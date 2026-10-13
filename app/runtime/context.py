"""Personal context v1 (roadmap batch 2): long-term memory sorted into domains, and the few facts that matter for a
request handed to the agent at the start of the task, so it does not ask the user again for things it already knows
(shoe size, cabin class, preferred cuisine, which mailbox to send from …).

Domains (域):
  person      人物与关系      people the user deals with and how they relate (colleagues, travel companions, family)
  preference  偏好            likes, sizes, styles, cuisines, cabin class, formats
  place       地点            home / office / city / time zone
  account     账户与会员      mailboxes, memberships, subscriptions, phone lines (numbers themselves live in the vault)
  site        网站习惯        how a given website works for the user (guest checkout, phone format, delivery option)
  rule        默认规则        standing instructions for OMuse ("always …", "never …", spend caps, fixed routines)
  work        工作与其他      companies, projects, everything else

Selection is deterministic (no model call): what the request is about (shopping, dining, travel, email …), names and
sites it mentions (with aliases: 迪卡侬 = Decathlon = decathlon.sg), and shared words. Facts learned by OMuse itself
(not stated by the user) are "pending" until the user confirms them on the Memory page; they are still used, marked
"unconfirmed".
"""
from __future__ import annotations

import re

DOMAINS = [
    ("person", "人物与关系", "People"),
    ("preference", "偏好", "Preferences"),
    ("place", "地点", "Places"),
    ("account", "账户与会员", "Accounts & memberships"),
    ("site", "网站习惯", "Site habits"),
    ("rule", "默认规则", "Rules & defaults"),
    ("work", "工作与其他", "Work & other"),
]
DOMAIN_KEYS = [d[0] for d in DOMAINS]
DOMAIN_LABEL = {k: f"{zh} {en}" for k, zh, en in DOMAINS}

# ------------------------------------------------------------------ classification
_EMAIL_ADDR = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_WEBSITE = re.compile(r"\b[a-z0-9-]+\.(?:com|sg|co|net|org|io|my|hk|cn|jp|uk|de)(?:\.[a-z]{2})?\b", re.I)
_SITE_HOW = re.compile(r"网站|网页|结账|结算|付款页|下单页|访客|登录|注册|填写|格式|表单|送货到家|checkout|guest|log ?in|sign ?in|"
                       r"form|format|field|delivery option|home delivery|accepts|without \+|8 digits|位数", re.I)
_RULE = re.compile(r"以后|每次|总是|一律|默认|上限|不超过|不要|别再|必须|先问|先确认|固定流程|"
                   r"\b(always|never|whenever|every time|by default|default to|must|do not|don't|avoid|limit|cap|at most|"
                   r"ask (me |the user )?(first|before))\b|the assistant|OMuse|助手", re.I)
_PERSON = re.compile(r"同事|同行|家人|太太|老婆|丈夫|老公|孩子|儿子|女儿|父母|爸|妈|朋友|老板|助理|秘书|"
                     r"\b(travels? with|colleague|collaborat\w*|works? with|wife|husband|son|daughter|kids?|family|friend|"
                     r"boss|assistant to|partner|manager)\b", re.I)
_PLACE = re.compile(r"地址|住在|住址|邮编|办公室|公司地址|城市|时区|located at|\blives? in\b|(home|office|work|street|postal|mailing) address|address (is|at)|postal|\bRd\b|road|street|"
                    r"avenue|time ?zone|SGT|UTC|\bhome\b|office", re.I)
_ACCOUNT = re.compile(r"账户|账号|会员|积分|订阅|邮箱|手机号|电话号码|号码是|\b(account|membership|member|subscription|"
                      r"loyalty|points|krisflyer|mailbox|email accounts?|phone (number|line))\b", re.I)
_PREF = re.compile(r"喜欢|偏好|偏爱|爱吃|常用|习惯|尺码|鞋码|\d+码|身高|体重|只要|想要|\b(prefer\w*|likes?|enjoys?|wants?|favou?rite|interested|size|uses)\b", re.I)


def domain_of(fact: str, category: str = "", entity: str = "") -> str:
    """Best-guess domain for a fact (the user can change it on the Memory page)."""
    text = f"{fact} {entity}"
    plain = _EMAIL_ADDR.sub(" ", text)
    cat = (category or "").lower()
    if cat in ("place", "account", "site", "rule", "work"):     # set by the user / the tidy job
        return cat
    if (_WEBSITE.search(plain) or re.search(r"网站|website", plain, re.I)) and _SITE_HOW.search(plain):
        return "site"
    if _RULE.search(plain) and cat != "person":
        return "rule"
    if cat == "person":
        return "person"
    if cat in ("company", "project"):
        if _PLACE.search(plain) and re.search(r"located|地址|address", plain, re.I):
            return "place"
        if _ACCOUNT.search(text):
            return "account"
        return "preference" if re.search(r"prefer|interested in (buying|purchasing|dining)|enjoys?|喜欢|偏好", plain, re.I) else "work"
    if _PERSON.search(plain):
        return "person"
    if _PLACE.search(plain):
        return "place"
    if _ACCOUNT.search(text):
        return "account"
    if cat in ("preference", "habit") or _PREF.search(plain):
        return "preference"
    return "work"


# ------------------------------------------------------------------ what a request is about
INTENTS: dict[str, tuple[str, str]] = {
    # name: (request mentions …, facts that matter for it mention …)
    "shopping": (r"买|购|下单|订购|购物车|挑(一|个|件|双|支|款|几)|选(一|个|件|双|支|款)|推荐.{0,8}(款|个|件|双|支)|送人|礼物|"
                 r"\b(buy|purchase|order|shop|cart|gift)\b",
                 r"送货|\bdeliver(y|ed)?\b|结账|checkout|访客|guest|注册|个人信息|personal information|shops? on|购物|预算|budget"),
    # what is being bought decides which sizes / devices / tastes matter
    "wear": (r"鞋|靴|衣|裤|裙|外套|夹克|t恤|衬衫|袜|帽|\b(shoes?|sneakers?|boots?|shirts?|t-shirt|tee|jacket|pants|dress|socks)\b",
             r"尺码|鞋码|\d+码|身高|体重|\bsize\b|\bcm\b|\bkg\b"),
    "phone_gear": (r"手机|iphone|充电|耳机|\b(phone|case|charger|earbuds|airpods)\b",
                   r"iphone|手机壳|phone cases?|otterbox|android|pixel|galaxy"),
    "pen": (r"笔|钢笔|\bpens?\b", r"笔|\bpens?\b"),
    "dining": (r"餐厅|吃饭|晚饭|午饭|晚餐|午餐|订位|订座|订台|饭店|\b(restaurant|dinner|lunch|brunch|book a table|cuisine)\b",
               r"菜|cuisine|口味|吃|餐|restaurant|dining|chope|饮食|素食|vegetarian|辣|spicy|japanese|日本|湘|hunan"),
    "travel": (r"机票|航班|飞往|飞去|出差|旅行|旅游|酒店|住宿|行程|签证|\b(flights?|fly|hotels?|trip|travel|itinerary)\b",
               r"航班|flight|直飞|\bdirect\b|舱|\bclass\b|座位|seat|酒店|hotel|精品|boutique|安静|quiet|同行|travels? with|companion|"
               r"一起|签证|护照|krisflyer|airline|航空"),
    "email": (r"邮件|邮箱|回复|回信|写信|草稿|\b(e-?mail|mail|reply|draft)\b",
              r"邮箱|e-?mails?|mail|发件|sending|签名|signature|bytetradelab|sixwings"),
    "meeting": (r"会议|开会|日历|约(他|她|一下|个)|\b(meeting|calendar|appointment)\b",
                r"日历|calendar|时区|time ?zone|sgt|会议|meeting"),
    "report": (r"报告|简报|总结|汇总|新闻|周报|日报|\b(report|brief|summary|news|digest|pdf)\b",
               r"pdf|报告|\breports?\b|中文|chinese|格式|\bformat\b|新闻|\bnews\b|deliverables?"),
    "outdoor": (r"徒步|爬山|远足|跑步|健身|\b(hike|hiking|trail|run|running|exercise|workout)\b",
                r"徒步|hik|强度|intensity|小时|hours"),
    "phone": (r"打电话|致电|电话给|\b(call|phone)\b", r"电话|phone|号码|number"),
    "form": (r"填表|表格|表单|报名|\b(form|apply|sign ?up|register)\b",
             r"地址|address|电话|phone|邮箱|e-?mail|姓名|name|公司|company|个人信息|personal information|注册"),
    "unsubscribe": (r"退订|取消订阅|广告邮件|垃圾邮件|\b(unsubscribe|newsletters?|spam|promotions?)\b",
                    r"退订|unsubscribe|已读|as read|non-important"),
}
_INTENT_RX = {k: (re.compile(a, re.I), re.compile(b, re.I)) for k, (a, b) in INTENTS.items()}

# merchants and services people name in different ways
ALIASES: list[list[str]] = [
    ["decathlon", "迪卡侬", "decathlon.sg"], ["amazon", "亚马逊", "amazon.sg"], ["shopee", "虾皮"], ["lazada", "来赞达"],
    ["taobao", "淘宝"], ["jd.com", "京东"], ["singapore airlines", "新航", "新加坡航空", "singaporeair", "krisflyer"],
    ["scoot", "酷航"], ["grab"], ["chope"], ["notion"], ["uniqlo", "优衣库"], ["ikea", "宜家"], ["fairprice", "职总平价"],
]

_STOP = {"the", "user", "users", "and", "for", "with", "that", "this", "from", "their", "they", "are", "has", "have", "was",
         "who", "about", "into", "when", "will", "not", "but", "any", "all", "can", "you", "your", "our", "his", "her",
         "帮我", "一下", "我的", "用户", "一个", "这个", "那个", "可以", "需要", "看看", "给我", "什么"}


def intents(text: str) -> list[str]:
    return [k for k, (ask, _) in _INTENT_RX.items() if ask.search(text or "")]


def tokens(text: str) -> set[str]:
    t = (text or "").lower()
    out = {w for w in re.findall(r"[a-z][a-z0-9.+-]{2,}", t) if w not in _STOP}
    for run in re.findall(r"[一-鿿]{2,}", t):
        out.update(run[i:i + 2] for i in range(len(run) - 1))
    return {w for w in out if w not in _STOP}


def _alias_groups(entities: list[dict]) -> list[list[str]]:
    groups = [list(g) for g in ALIASES]
    for e in entities or []:
        names = [e.get("name") or ""] + list((e.get("attrs") or {}).get("aliases") or []) + [e.get("relation") or ""]
        names = [n.strip() for n in names if n and len(n.strip()) >= 2]
        if names:
            groups.append(names)
    return groups


_HOST = re.compile(r"\b([a-z0-9-]{3,})\.(?:[a-z]{2,6})(?:\.[a-z]{2})?\b", re.I)


def named(text: str, entities: list[dict] | None = None) -> list[list[str]]:
    """Alias groups the text mentions (迪卡侬 → [decathlon, 迪卡侬, decathlon.sg]); a website named by its address
    counts too (shop.test → [shop.test, shop])."""
    low = (text or "").lower()
    out = [g for g in _alias_groups(entities or []) if any(a.lower() in low for a in g)]
    for m in _HOST.finditer(_EMAIL_ADDR.sub(" ", low)):
        if not any(m.group(1) in a.lower() for g in out for a in g):
            out.append([m.group(0)] + ([m.group(1)] if len(m.group(1)) >= 5 else []))
    return out


def _mentions(fact_text: str, group: list[str]) -> bool:
    low = fact_text.lower()
    return any(a.lower() in low for a in group)


# identity documents (passport number / expiry, ID card, date of birth …): only when the request needs them filled in
_ID_DOC = re.compile(r"护照|身份证|出生日期|生日|签发|有效期至|证件号|\b(passport|date of birth|DOB|born on|national id|NRIC|FIN|"
                     r"id (card|number)|identity card|expir(y|es|ation))\b", re.I)
_NEEDS_ID = re.compile(r"填写|填表|表格|表单|申请|值机|登机|旅客信息|乘客信息|入住登记|护照.{0,6}(到期|过期|有效|续)|证件|"
                       r"\b(form|apply|application|check-?in|passenger (details|info)|traveller details|renew)\b", re.I)


def needs_id(request: str) -> bool:
    return bool(_NEEDS_ID.search(request or ""))


_TRIGGER = re.compile(r"(?:说|says?|ask(?:s)? for)\s*[「“\"']([^」”\"']{2,20})[」”\"']")
GENERAL_RULE = re.compile(r"the assistant|OMuse|助手|autonomous|自主|直接执行", re.I)


def select(request: str, facts: list[dict], entities: list[dict] | None = None, limit: int = 12,
           context: str = "") -> list[dict]:
    """The facts that matter for this request, best first. Each returned fact gets `score` and `why`.
    `context` = the recent conversation (a follow-up like "好，就买那双" carries little on its own)."""
    req = request or ""
    whole = f"{req}\n{context}" if context else req
    its = intents(req) or intents(context)
    groups = named(whole, entities)
    rtoks = tokens(req)
    want_id = needs_id(req)
    scored = []
    for f in facts:
        text = f"{f.get('fact') or ''} {f.get('entity') or ''}"
        if not want_id and _ID_DOC.search(f.get("fact") or ""):
            continue        # passport / ID / birth date stay out of answers unless a form needs them
        dom = f.get("domain") or domain_of(f.get("fact") or "", f.get("category") or "", f.get("entity") or "")
        s, why = 0.0, []
        trig = _TRIGGER.findall(f.get("fact") or "")
        if dom == "rule" and trig:      # "以后每次说「准备出差」…": only when the user says it
            if any(t and t in req for t in trig):
                scored.append({**f, "domain": dom, "score": 10.0, "why": "触发词：" + trig[0]})
            continue
        g = [x for x in groups if _mentions(text, x)]
        if g:
            s += 6
            why.append("提到 " + g[0][0])
        hits = [k for k in its if _INTENT_RX[k][1].search(text)]
        if hits:
            s += 3 + min(2, len(hits) - 1)
            why.append("相关：" + "/".join(hits))
            if dom == "site" and not g:
                s -= 2       # a site habit matters when that site is in play
        shared = rtoks & tokens(text)
        if shared:
            s += min(3, len(shared))
            if not why:
                why.append("词：" + ",".join(sorted(shared)[:3]))
        if dom == "rule" and GENERAL_RULE.search(text):
            s += 3
            why.append("通用规则")
        if s >= 3:
            scored.append({**f, "domain": dom, "score": s + min(1.0, (f.get("uses") or 0) / 50.0), "why": "；".join(why)})
    scored.sort(key=lambda x: -x["score"])
    return scored[:limit]


def render(selected: list[dict], en: bool = False) -> str:
    """Grouped by domain, for the prompt."""
    if not selected:
        return "(nothing on file that bears on this request)"
    by: dict[str, list[str]] = {}
    for f in selected:
        mark = " (unconfirmed — learned in an earlier task)" if f.get("status") == "pending" else ""
        by.setdefault(f.get("domain") or "work", []).append(f"- {f['fact']}{mark}")
    out = []
    for k in DOMAIN_KEYS:
        if k in by:
            out.append(f"[{DOMAIN_LABEL[k].split(' ', 1)[1] if en else DOMAIN_LABEL[k]}]")
            out.extend(by[k])
    return "\n".join(out)


USE_RULE = ("Use these directly — do NOT ask the user again for anything listed here (sizes, cabin class, cuisine, which "
            "mailbox, delivery habits …); say in your answer which of them you applied. Ask only for what is really "
            "missing, and memory_search before asking about the user's own preferences. Apply a fact only when the request "
            "is about it: for a general question (weather, visas, what to pack, sights) do not assume who travels with "
            "the user, group size or a business purpose, and never repeat document numbers, birth dates, family "
            "members' full names or passport details in the answer unless the user asked for them. Bookings found in "
            "e-mails marked as test / fictional are not the user's real plans.")


def site_name(url: str) -> str:
    """'https://www.decathlon.sg/p/123' → 'decathlon'."""
    m = re.match(r"^[a-z]+://([^/:?#]+)", (url or "").strip().lower())
    if not m:
        return ""
    parts = [p for p in m.group(1).split(".") if p not in ("www", "m")]
    if len(parts) >= 3 and parts[-2] in ("com", "co", "org", "net", "gov", "edu"):
        parts = parts[:-2]
    elif len(parts) >= 2:
        parts = parts[:-1]
    return parts[-1] if parts else ""


def site_facts(url: str, facts: list[dict]) -> list[dict]:
    """Site habits (and other facts) about the website at `url`."""
    name = site_name(url)
    if len(name) < 3:
        return []
    group = next((g for g in ALIASES if any(a.lower().split(".")[0] == name for a in g)), [name])
    out = []
    for f in facts:
        text = f"{f.get('fact') or ''} {f.get('entity') or ''}".lower()
        if any(a.lower() in text for a in group):
            dom = f.get("domain") or domain_of(f.get("fact") or "", f.get("category") or "", f.get("entity") or "")
            if dom in ("site", "account", "rule", "preference"):
                out.append({**f, "domain": dom})
    out.sort(key=lambda f: (f["domain"] != "site", -(f.get("uses") or 0)))
    return out[:5]
