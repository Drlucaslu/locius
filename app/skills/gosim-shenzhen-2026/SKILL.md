---
name: gosim-shenzhen-2026
description: 深圳 GOSIM 2026 大会助手（10 月 16–17 日，含 RustChinaConf 与 Spotlight）：查讲者、议程、正在进行和即将开始的场次，按兴趣推荐并做调研 GOSIM Shenzhen 2026 (Oct 16–17, with RustChinaConf Oct 15–17 and Spotlight): look up any speaker, session or event, what is on now and next (China time), recommend sessions and people to meet from the user's interests, build a personal agenda, research a talk or speaker.
---
# GOSIM Shenzhen 2026 / GOSIM 深圳 2026

The catalog below (every session, speaker and Spotlight project, with the RustChinaConf programme) is the source
of truth for names, times and rooms; the sites are for details that are not in it. Three events share one venue
on Oct 16–17:
- **GOSIM Shenzhen 2026** — Oct 16–17, ADEN Hotel Shenzhen Nanshan (No. 8 Guishan Road, Shekou, Nanshan;
  700 m from Sea World metro, Lines 2/8/12). 150+ speakers, 2,000+ developers; keynote plenary each morning in
  3F ADEN (full hall), then parallel tracks: Agentic AI Summit, Agentic AI on Edge, Agentic OS & App, Open Source
  Models & Infra, Open Source Robotics, Agentic Device, plus workshops/forums (vLLM, DORA, KVCDN, CANN, openGauss,
  AI Education, Google Cloud, Rust instructor training). Site: https://shenzhen2026.gosim.org (schedule at /schedule/).
- **RustChinaConf 2026** — Oct 15 workshop day (ONES Venue, 20F Tower A Gemdale Viseen Center, Nanshan — and the
  ADEN Hotel; the two are ~40 min apart) and Oct 16–17 at the ADEN Hotel: its attendees join the GOSIM keynote,
  then a Rust morning plenary and three afternoon tracks (Qihang 1/2/3); tea break 15:45–16:00 shared with GOSIM.
  Site: https://rustchinaconf.org/schedule (Chinese: /zh-CN/schedule).
- **Spotlight Shenzhen 2026** — 18 selected AI-native hardware/agent products with booths on both days and a
  main-stage showcase slot. Site: https://spotlight.gosim.org/shenzhen2026/.

## Time: everything is China Standard Time (CST, UTC+8, no DST)
1. The status note gives the current time in the user's time zone. Convert it to CST before saying what is on:
   CST = UTC+8, so e.g. 18:30 PDT (UTC−7) = 09:30 CST next day; 20:00 CEST (UTC+2) = 02:00 CST next day;
   Asia/Shanghai, Hong Kong, Singapore, Taipei = CST already. State the CST time you used ("It is 10:42 CST, Fri Oct 16").
2. "Now": sessions whose start ≤ CST time < end, on today's CST date. "Next": sessions starting within the next
   90 minutes, soonest first; across tracks, show one line per track. Before Oct 15 say how many days until the
   event; after Oct 17 say it is over and offer recordings/slides research.
3. Always print times as CST with the date, and add the user's local time in brackets when they are elsewhere.

## Answering
- **Look-ups** ("who is X", "when is the talk on Y", "what is in the robotics track on Friday"): answer from the
  catalog with time, room, speakers and the one-line gist; give the session URL. Match names loosely (pinyin,
  surname-first order, company names).
- **Interests first.** When asked for recommendations, an agenda or "who should I meet", ask up to three short
  questions in one message if not already known or in memory: (a) topics (agents, edge/on-device, models & infra,
  robotics, Rust, devices, AI education, products), (b) goal (learn, hire, find partners/customers, raise or invest,
  speak/press), (c) which days and whether they prefer talks, workshops or hallway time. Then recommend without
  asking again; save the stated interests as a fact in memory.
- **Recommendations**: per day, up to 8 sessions ranked by fit, no two at the same time (say what the alternative
  is), with the keynote block, lunch and the 15:45 tea break as anchors; for "people to talk to" list 5–10 speakers
  with why (their talk, company, role), when and where to find them (right after their session, at the speaker
  lounge, at a Spotlight booth), and their public links from the catalog. Prefer people whose talk matches the goal
  (e.g. for hiring: engineers at companies in the user's field; for partnerships: founders and maintainers).
- **Agenda**: a table per day (CST time · session · room · why), with walking notes (2F vs 3F rooms), and offer to
  put it in the user's calendar if Calendar is connected (events in Asia/Shanghai).
- **Research** a session or speaker (deep research when asked): browser_read the session page (full abstract) and
  the speaker page, then the speaker's links (GitHub, X, LinkedIn, company), then a browser_search for recent talks,
  papers or releases; summarise what they work on, what to ask them, and recent news (with dates). For a company,
  also what they are hiring/selling. Never invent contact details: give only links that appear on the sites or
  that you read on the person's own page; no email or phone guessing.
- **Spotlight**: match projects to interests, give the booth hint (demo area, both days) and the project link.
- **Changes**: the catalog is a snapshot (date below). If the user asks whether a session is still on, or a time
  looks wrong, browser_read the schedule page (GOSIM /schedule/, or rustchinaconf.org/schedule) and report the
  difference. Tickets, visa and travel questions: the GOSIM site has /general-travel/ and /chinese-visa/; the
  `shenzhen` skill covers the city.
- Reply in the user's language; keep talk titles in English as published, and add 中文 when the user writes Chinese.

<!-- catalog:start -->
_Catalog snapshot 2026-10-12 from the three sites above; breaks and lunches omitted. Session URL: https://shenzhen2026.gosim.org/schedule/<id>/ · speaker URL: https://shenzhen2026.gosim.org/speakers/<id>/._

## GOSIM Shenzhen 2026 — sessions by day and track (CST)

### Fri Oct 16 · Agentic AI Infrastructure Forum · 2F – KAI XUAN 2
- 14:00–14:35 **Running Millions of Agents at Tencent: CubeSandbox as the Hands Behind the Harness Brain** — Feynman Zhou (CNCF Ambassador，Senior Product Manager for Tencent Cloud). Abstract to be announced. `ascend-cubesandbox`
- 14:35–15:10 **vLLM and Ascend: Plugin-Based Architecture and MoE   Expert Load Balancing in Practice** — Frey Tian (Huawei Ascend Computing Inference Technology Expert, Huawei). Abstract to be announced. `ascend-vllm-moe`
- 15:10–15:45 **From Rollout to Weight Synchronization: How Mooncake Supports High-Performance RL and Inference** — Teng Ma (Maintainer, Mooncake Community). Abstract to be announced. `ascend-mooncake-rl`
- 16:00–16:30 **Triton For Ascend：Simplifying High-performance Operator Development** — Fu Bingyang (Triton Operator Technical Expert, Huawei). Abstract to be announced. `ascend-triton`
- 16:30–17:00 **AscendNPU IR: Building an efficient and easy-to-use Ascend diverse operator system, empowering developers to innovate flexibly** — Wu Lingfei (AscendNPU IR Technical Expert, Huawei Compiler Lab). Abstract to be announced. `ascend-npu-ir`
- 17:00–17:30 **KunPeng SuperPoD - New Computing Infrastructure for the Agentic AI** — Wang Yajun (Kunpeng AI Agent Technical Expert). Abstract to be announced. `ascend-kunpeng-superpod`

### Fri Oct 16 · Agentic AI Summit · 3F – ADEN 1
- 10:15–10:40 **The New Developer Ecosystem in Agentic Era** — Jianzhong Li (President, Singularity Intelligence Research Institute / Senior Vice President, CSDN). Agents are transforming not only the application paradigm, but also the developer ecosystem. `p-125-agent-产品范式创新的若干命题-key-propositions-for-agent-product-paradigm-innovation`
- 10:40–11:05 **State of Harness Engineering** — Birgitta Böckeler (Distinguished Engineer). State of harness engineering explores the challenges of effectively managing coding agents. `p-57-state-of-harness-engineering`
- 11:05–11:30 **Agent-Centric Engineering — From Personal Productivity to Organizational Capability** — Sean Dong (Program Director, Huawei Programming Language Lab). This talk presents Agent-Centric Engineering (ACE), a framework for turning individual AI-assisted productivity into organizational … `p-56-agent-centric-engineering-from-personal-productivity-to-organizational-capability`
- 11:30–12:00 **Open source, Openness and Standardization of Large Models** — Liyun Yang (Director, Open Source Research Office, China Electronics Standardization Institute). Current Status of China’s Open‑Source Large‑model Industry and Standardization Research Achievements on Openness Grading Specification for … `p-189-open-source-openness-and-standardization-of-large-models`
- 14:00–14:25 **Knowledge as Code: A New Collaboration Architecture for AI-Native Teams** — Sunny Gao (Founder & CEO, MindMux.ai). As AI agents become active participants in software development, research, and knowledge work … `p-166-knowledge-as-code-a-new-collaboration-architecture-for-ai-native-teams`
- 14:25–14:50 **From “Identity Blind Spots” to “Certified Agents”: Key Challenges and Industry Responses in Agent Identity Security** — Tingsheng Fu (Senior Vice President, AsiaInfo Security). As autonomous agents become digital workers, conventional identity management designed for people is no longer sufficient. `p-206-从-身份盲区-到-持证上岗-智能体身份安全的关键挑战与产业应对`
- 14:50–15:15 **Self-Evolving Apps: Building Software That Gets Smarter Every Time You Use It** — Tiberiu Socaci (CEO & Co-Founder, Makeitfuture). Self-evolving apps improve with each use by learning from user corrections, not through code updates. `p-18-self-evolving-apps-building-software-that-gets-smarter-every-time-you-use-it`
- 15:15–15:40 **Agent First, Workflow Later: Enterprise Agentic AI Practices with DeerFlow** — Willem Jiang (Chief Technical Consultant, Singularity Intelligence Research Institute; AI Agent Expert). Drawing on DeerFlow deployments in large enterprises, this talk explains how to build a Super Agent environment with reusable skills … `p-113-agent-first-workflow-later-deerflow-的企业级智能体实践`
- 15:40–16:05 **Building a Knowledge-Work Harness: From Coding Agents to Executable Strategy** — Igor Schwarzmann (Principal, Known Unknowns GmbH). Building a knowledge-work harness requires addressing the verification gap, as decisions lack the automated checks found in coding. `p-40-building-a-knowledge-work-harness-from-coding-agents-to-executable-strategy`
- 16:05–16:30 **From Agent Design Patterns to Engineering Implementation: Architecture and Practices of Execution-Oriented Agents** — Jia Huang (Chief Technical Consultant, Singularity Intelligence Research Institute). Enterprise AI upgrades usually begin with existing business capabilities, interfaces, and workflows. `p-198-从-agent-设计模式到工程落地-执行型智能体的架构与实践`
- 16:30–16:55 **Semantic Croissant, QueryGraph and the Cross-Domain Interoperability Framework (CDIF)** — Slava Tykhonov (Head of AI & Interoperability, CODATA). This talk presents a three-layer architecture for trustworthy, AI-ready data. `p-174-semantic-croissant-querygraph-and-the-cross-domain-interoperability-framework-cdif`
- 16:55–17:20 **2026: The “Memory Inflection Point” for AI Glasses** — Yi Ru (Founder & CEO, Lawaken Technology). As AI glasses move toward the mass market, competition is shifting from the number of features to the depth of memory. `p-110-2026-ai眼镜的-记忆拐点`

### Fri Oct 16 · Agentic AI on Edge · 3F – MING HUA
- 10:15–10:50 **How Do You Read a Million Tokens on Your Laptop? You Don't.** — Iaroslav Neverov (Full-stack Engineer, Pleias). This session explores on-device agentic knowledge work under strict memory and model-size constraints. `p-106-how-do-you-read-a-million-tokens-on-your-laptop-you-don-t`
- 10:50–11:25 **From Components to Complete Machines: The Path to Scaling Up Edge AI Liquid-Cooled Computing Devices** — An Chen (Co-founder, Chairman & CEO, Shenzhen Zhiweitong Technology). This talk examines how liquid-cooled edge AI computing equipment can move from component-level breakthroughs to scalable complete systems. `p-109-从部件到整机-端侧ai液冷算力设备的规模化落地路径`
- 11:25–12:00 **KTransformers: The Fine-Tuning-to-Inference Closed Loop for Full-Precision 1T-Class MoE Models on Consumer Hardware** — Peilin Li (Ph.D. Student, Tsinghua University / Approaching AI); Yujie Yang (Co-speaker). KTransformers enables efficient local inference for 1T-class MoE models on consumer hardware by leveraging CPU-GPU heterogeneous computing. `p-3-ktransformers-the-fine-tuning-to-inference-closed-loop-for-full-precision-1t-class-moe-models-on-consumer-hardware`
- 14:00–14:35 **OpenCV 5: What's New—and How to Prepare Your Company for the Upgrade** — Satya Mallick (CEO, OpenCV.org). OpenCV 5 represents a major modernization of the leading open-source computer vision library, introducing updates to its foundation … `p-26-opencv-5-what-s-new-and-how-to-prepare-your-company-for-the-upgrade`
- 14:35–15:10 **Makepad AI Hub: accessing local AI from your own device cloud** — Rik Arends (Co-Founder, Makepad). This talk demonstrates Makepad AI Hub, which shares local AI compute across a person's devices. `p-175-makepad-ai-hub-accessing-local-ai-from-your-own-device-cloud`
- 15:10–15:45 **RustNN at the Edge: WebNN as Infrastructure for Local AI Agents** — Markus Tavenrath (Principal Engineer, Developer Technology, NVIDIA). RustNN and the W3C WebNN standard provide a unified solution for running AI agents locally. `p-37-rustnn-at-the-edge-webnn-as-infrastructure-for-local-ai-agents`
- 16:00–16:30 **Building Hybrid AI Systems: Edge Inferencing Meets Cloud Reasoning** — Frank Fan (Principal Solutions Architect, AWS). Using warehouse safety monitoring as a case study, this talk presents a hybrid architecture that runs latency-sensitive vision-language … `p-157-building-hybrid-ai-systems-edge-inferencing-meets-cloud-reasoning`
- 16:30–17:00 **Observations on the Technical Development of Edge Intelligence and the Open-Source MiniCPM Ecosystem** — Cenzhe Chase Jing (Head of Open Source Ecosystem, ModelBest). This talk surveys the current development of on-device intelligence and related industry trends. `p-105-端侧智能的技术发展与-minicpm-开源生态实践观察`
- 17:00–17:30 **Effective and High-Performance Human-Agent Interaction** — Gregory Terzian (Founder, FOSS (Shanghai) Technology Consulting). Using uni03C0, a macOS client for the Pi coding agent, this talk explores how human–agent interfaces can move beyond chat and terminal … `p-77-effective-and-high-performance-human-agent-interaction`

### Fri Oct 16 · Agentic Device · 2F – KAI XUAN 1
- 10:15–10:50 **openvela: From an Open-Source OS to the Foundation for AI Hardware Agents** — Chao Du (openvela Project Lead, Xiaomi). This session introduces openvela, Xiaomi's open-source AIoT operating system, and its evolution into a foundation for AI hardware agents. `p-112-openvela-从开源操作系统到-ai-硬件智能体的基础底座`
- 10:50–11:25 **How Open-Source Hardware Brings AI from the Cloud into Daily Life** — Tong Ling (Head of IoT Product Commercialization, Espressif Systems). Tong Ling discusses how open-source hardware brings AI from the cloud into daily life. `p-89-tbd`
- 11:25–12:00 **From Connecting to Thinking: TuyaOpen's Agent-First OS for the Physical AI Era** — Hsuan Han Lai (Lead of Developer Ecosystem, Tuya Smart Inc). TuyaOpen introduces an open-source A-IoT operating system designed for the Physical AI era … `p-75-from-connecting-to-thinking-tuyaopen-s-agent-first-os-for-the-physical-ai-era`
- 14:00–14:35 **From Device Connectivity to Collaboration: An A2A Distributed Smart-Hardware Network with EMQ Device Agent** — Fahua Jin (Co-Founder & CTO, EMQ). The talk discusses how EMQ Device Agent transforms physical devices into AI agents with command, property, and event semantics … `p-59-from-device-connectivity-to-device-collaboration-building-an-a2a-distributed-intelligent-hardware-network-with-emq-device-agent`
- 14:35–15:10 **Physical Interfaces for Agentic Development** — Michael Yuan (Founder of Second State & Co-Founder of GOSIM); Siheng Chen (Engineer, Second State). This talk explores dedicated hardware for supervising multiple coding agents without constant context switching. `p-154-physical-interfaces-for-agentic-development`
- 15:10–15:45 **From Understanding You to Seeing You — Real-Time Multimodality Brings AI into the Real World** — Xiaodong Feng (Head of the Physical AI Product Line, Agora). Over the past two years, large language models have transformed AI from a tool that follows commands into a conversational partner. `p-69-open-source-hardware-integration-practices-for-agora-conversational-ai`
- 16:00–16:30 **Agentic AI as a Contributor to Mobile Linux** — Bardia Moshiri (Embedded Software Engineer, Furi Labs); Wayne Connolly (COO, FuriLabs). Agentic AI is helping simplify contributions to Mobile Linux by assisting with code understanding, navigation, debugging … `p-62-agentic-ai-as-a-contributor-to-mobile-linux`
- 16:30–17:00 **IterxAI by Ciyuan Kaiwu — Hardware Vibe Coding** — Zhenyu Yang (Founder and CEO, Shenzhen Ciyuan Kaiwu Technology Co., Ltd.). This talk presents IterxAI, an end-to-end environment designed to help beginners create hardware prototypes. `p-162-词元开物iterxai-硬件vibe-coding`
- 17:00–17:30 **From 'Wearable' to 'Understanding You': Productizing AI Agent Devices for Real-World Scenarios** — Baofeng Wang (Co-founder, Shanghai Mood Perception Intelligence Technology). Drawing on product work in brain–computer interfaces and AI wearables, this talk explores how agentic devices can continuously sense user … `p-104-从-可穿戴-到-懂你-ai-智能体设备的产品化与场景落地`

### Fri Oct 16 · Agentic OS & App · 2F – HAI XIA 2
- 10:15–10:50 **Agentic Harness Engineering: Observability-Driven Automatic Evolution of Coding-Agent Harnesses** — Jiahang Lin (Master's Student, Fudan University). This talk presents Agentic Harness Engineering, a closed loop for automatically improving coding-agent harnesses. `p-139-agentic-harness-engineering-observability-driven-automatic-evolution-of-coding-agent-harnesses`
- 10:50–11:25 **PenguinHarness: Efficient Self-Evolving Agent Harness for 1000+ Models** — Yaowei Zheng (Co-Founder & CTO, PrismShadow). PenguinHarness is an open-source self-evolving agent framework developed by the LlamaFactory team … `p-81-penguinharness-an-efficient-self-evolving-agent-harness-for-1-000-models`
- 11:25–12:00 **A New Era of Inventors** — Hunter Bown (Founder, ShannonTek). This talk asks how agentic AI can help more people turn observations and ideas into testable creations. `p-155-a-new-era-of-inventors`
- 14:00–14:35 **AI-Native Company Operating System: How Open Source Agents Transform Startup Workflows** — Jacky Hsu (Founder & CEO, Ingora). AI is transforming how companies are organized, moving from traditional human-centric structures to AI-native systems where knowledge is … `p-21-ai-native-company-operating-system-how-open-source-agents-transform-startup-workflows`
- 14:35–15:10 **SpecArtisans: A Verifiable Spec-Driven Development Paradigm for AI Coding** — Zixi Liu (Senior Engineer, Huawei). SpecArtisans is a Spec-Driven development paradigm for AI programming, aiming to ensure AI accurately follows original requirements … `p-58-specartisans-a-verifiable-spec-driven-development-paradigm-for-ai-coding`
- 15:10–15:45 **Agentic in Game AI, did we get any far?** — Fanshi Zhang (CTO, Moeru AI); Claudia Wang (Senior Algorithm Engineer, Moeru AI Ltd.). This talk demonstrates progress in applying agentic AI to games and discusses how the demonstrations can be extended into environments and … `p-72-agentic-ai-in-games-how-far-have-we-come`
- 16:00–16:30 **How to Use Harness Engineering to Build an AI Mini-Game Production Pipeline** — Justin Tan (Solutions Architect, Google Cloud). This talk presents an automated AI mini-game production pipeline built with Harness engineering, a two-layer automated review system … `p-114-如何运用harness工程打造ai小游戏制作管线`
- 16:30–17:00 **Two Decouplings: Bringing Coding Agents into Everyday Applications** — Weiyu Xie (Chief Architect, Approaching.AI). This talk presents two steps for moving coding-agent capabilities beyond programming. `p-145-两次解耦-把-coding-agent-带进日常应用`
- 17:00–17:30 **Your Agent's History Is Infrastructure, Not Logs — Building a Queryable Evidence Layer over Coding Agent Sessions** — Yuu (Agent Performance & Optimization Intern, Dify). Obelisk transforms scattered coding agent session histories into a unified, queryable infrastructure using SQLite and FTS5. `p-80-your-agent-s-history-is-infrastructure-not-logs-building-a-queryable-evidence-layer-over-coding-agent-sessions`

### Fri Oct 16 · DORA Workshop · 2F – KAI XUAN 2
- 10:15–10:30 **From Code to Robots: The Collaborative Journey of the DORA-rs Community and Practices in Embodied AI** — Yang Li (Technical Lead, DORA Community). This workshop shares how the DORA community connects open-source collaboration with real embodied-intelligence systems. `p-122-从代码到机器人-dora社区的共建之路与具身智能实践`
- 10:30–10:45 **A DORA-Based 3D Navigation Framework: From LiDAR Point Clouds to Trajectory Planning** — Qiuji Chen (Graduate Student, Chongqing University of Posts and Telecommunications). This talk walks through a complete 3D navigation stack on a real mobile robot, from raw LiDAR point clouds to wheel commands. `dora-qiuji-chen`
- 10:45–11:00 **Dataflow-Driven Robotic Navigation: From Perception to Control in the DORA-rs Architecture** — Wencheng Xiao (PhD Candidate, Shijiazhuang Tiedao University). This workshop examines DORA's dataflow-driven approach to robotic navigation, connecting perception and control through efficient … `p-176-dataflow-driven-robotic-navigation-from-perception-to-control-in-the-dora-architecture`
- 11:00–11:15 **Trust Is Not the Default: From DORA-rs Dataflow Debugging to Trustworthy Tool Design** — Keshu Han (Embodied AI Developer, Beijing Dora Intelligence). Keshu Han discusses trust in tool design through DORA-rs dataflow debugging. `p-118-dora-studio-a-gsoc-project-share-tentative`
- 11:15–11:30 **Key Technologies of Robotic Teleoperation Data Collection and Multimodal Closed-Loop Control under the DORA-rs Architecture** — Yujie Sun (R&D Engineer, Daorui Intelligent Technology (Beijing) Co., Ltd.). This workshop presents robotic teleoperation data collection and multimodal closed-loop control under the DORA architecture. `p-168-key-technologies-of-robotic-teleoperation-data-collection-and-multimodal-closed-loop-control-under-the-dora-architecture`
- 11:30–11:45 **A High-Speed Heterogeneous Data Transmission Framework for Robot-Side End-Edge-Cloud Collaboration** — Canran Tang (Graduate Student, University of Science and Technology of China). This session presents a unified data-transfer framework spanning CPU memory, GPU memory, local interconnects … `p-121-high-performance-heterogeneous-data-transfer-framework-for-end-edge-cloud-robot-inference`
- 11:45–12:00 **Lessons from Building an AI-Assisted DORA-rs Tutorial** — Qiyang Tan (Dev, Dora). Qiyang Tan shares lessons from building an AI-assisted DORA-rs tutorial. `p-188-robotic-learning-with-ai`
- 12:00–12:15 **From Agentic Programming to Automated Robotic Research** — Yongcheng Wei (PhD Student, Chongqing University of Posts and Telecommunications). This workshop examines what autonomous research requires when coding agents move from software environments to real robots. `p-151-从智能体编程走向机器人自动科研`

### Fri Oct 16 · Huawei CANN Workshop · 3F – HAI LIAO
- 10:15–10:20 **Opening Remarks** — Lixin Shao (General Manager of CANN business, Huawei). Opening remarks for the CANN Workshop by Lixin Shao. `cann-opening-remarks`
- 10:20–10:45 **DeepSeek’s Official Open-Source Building Blocks for Ascend, Jointly Building an Efficient, Developer-Friendly AI Chip Software Ecosystem** — Nan Zou (CANN Architect). Abstract to be announced. `cann-deepseek-ascend`
- 10:45–11:10 **Inside DeepEP / DeepGEMM: Accelerating MoE Communication and Matrix Computation for Large Models** — Jianjun Chen (ops-transformer Committer). Abstract to be announced. `cann-deepep-deepgemm`
- 11:10–11:35 **Inside TileLang / TileKernels: The Technology Behind TileLang’s Native Support for Ascend 950** — Yuchen Zhang (TileLang-Ascend Community Collaborator). Abstract to be announced. `cann-tilelang-tilekernels`
- 11:35–12:00 **Exploring the Agent-Friendly Paradigm: Generating High-Performance Complex Operators with CANNBot** — Zhiqiang Xiong (ops-transformer Committer). Abstract to be announced. `cann-agent-friendly-cannbot`

### Fri Oct 16 · Keynote Plenary · 3F – ADEN (full hall)
- 09:10–09:25 **Empowering a Connected Intelligent World: The Symbiotic Evolution of OpenHarmony and AI** — Haibo Chen (Chair, OpenHarmony Technical Steering Committee). Throughout history, operating systems have co-evolved with computing paradigms. `p-218-tbd`
- 09:25–09:40 **Keynote — Topic to Be Announced** — Mehdi Snene (Chief AI Officer, Digital infrastructure and emerging technologies, UN). Keynote by Mehdi Snene. The topic will be announced. `keynote-mehdi-snene`
- 09:40–09:55 **Open-Sourcing CANN to Foster Fertile Ground for AI Talent Development and Innovation** — Lixin Shao (General Manager of CANN business, Huawei). Open-Sourcing CANN to Foster Fertile Ground for AI Talent Development and Innovation `keynote-lixin-shao`

### Fri Oct 16 · Open Source Models & Infra · 3F – ADEN 2
- 10:15–10:50 **Rethinking Residual Connections: Toward Depth-Effective Language Model Scaling** — Shiwei Liu (Group Leader, Max Planck Institute for Intelligent Systems / ELLIS Institute Tübingen). Researchers explore whether recent residual-connection designs can enable effective depth scaling in language models. `p-6-rethinking-residual-connections-toward-depth-effective-language-model-scaling`
- 10:50–11:25 **Building and Evolution of the Ascend Open-Source Training Ecosystem** — Yongqiang Ma (Open-Source Training Software Expert, Huawei). As a computing power provider, embracing open-source communities and maintaining openness is essential to meet customer needs. `p-43-building-and-evolving-the-ascend-open-source-training-ecosystem`
- 11:25–12:00 **Scale-up Interconnect System for Supernodes** — Jiaqi Zheng (Associate Professor, Nanjing University). The talk discusses the challenges and optimizations in scaling up interconnect systems for supernodes … `p-8-scale-up-interconnect-system-for-supernodes`
- 14:00–14:35 **SynthCommonCorpus: the largest open synthetic pretraining corpus built for agentic models** — Anastasia Stasenko (Co-Founder & CEO, Pleias); Pieter Delobelle (Co-speaker). This talk introduces SynthCommonCorpus, an open synthetic pretraining corpus designed for agentic models and planned for release in autumn … `p-47-synthcommoncorpus-the-largest-open-synthetic-pretraining-corpus-built-for-agentic-models`
- 14:35–15:10 **Optimization of Edge-Side Inference Performance for Open-Source Large Models and Collaboration Between Agents** — Minako Kojima (Head of Developer Relations, Moonshot AI). Optimization of Edge-Side Inference Performance for Open-Source Large Models and Collaboration Between Agents With the rapid growth of edge … `p-204-optimization-of-edge-side-inference-performance-for-open-source-large-models-and-collaboration-between-agents`
- 15:10–15:45 **Mechanism Compliance Auditing and Inherent Security Hardening** — Quanshi Zhang (Associate Professor, Shanghai Jiao Tong University). The talk examines intrinsic security risks in large language models and explains why output-level constraints cannot guarantee trustworthy … `p-11-mechanism-based-compliance-auditing-and-intrinsic-security-hardening`
- 16:00–16:30 **From Adaptation to Co-Building: GLM’s Collaboration with the Open Source Community** — Yuxuan Zhang (Technology Evangelist, Zhipu AI). This talk reviews GLM's collaboration with inference communities including SGLang and vLLM. `p-22-从适配到共建-glm-与开源社区的协作实践`
- 16:30–17:00 **EvoPhys-World, the first 5D world model for Physical AGI** — Zhongxia Zhao (Co-Founder & COO, EvoPhys AI). This talk proposes EvoPhys-World, a five-dimensional world model that adds causal worldlines to three-dimensional space and time. `p-173-evophys-world-the-first-5d-world-model-for-physical-agi`
- 17:00–17:30 **KernelCAT: AI for Computing Practice Sharing** — Tian Ding (Founder, Zhizi Xinyuan). This talk explores how large AI models and mathematical optimization can accelerate operator development, model adaptation … `p-146-kernelcat-ai-for-computing实践分享`

### Fri Oct 16 · Open Source Robotics · 2F – HAI XIA 1
- 10:15–10:45 **Engineering an Open VLA Stack with DM0.5, OpenDM, and Dexbotic** — Haibin Zhang (AI Infrastructure & Open Source Lead, Dexmal). This talk presents the engineering practices behind DM0.5, OpenDM, and Dexbotic across the complete VLA lifecycle. `p-131-engineering-an-open-vla-stack-with-dm0-5-opendm-and-dexbotic`
- 10:45–11:15 **Co-building a New Paradigm of Physical Intelligence: Situation Awareness-based Jiuwen Symbiosis** — Jiahui Zhang (Expert, Huawei). This talk introduces Jiuwen Symbiosis, a Physical AI Agent framework that helps agents move from digital assistants to executors in the … `p-90-co-building-a-new-paradigm-of-physical-intelligence-situation-awareness-based-jiuwen-symbiosis`
- 11:15–11:45 **From the data factory to the world compiler** — Tristan Ruoli Dai (Founder/CEO, Noitom Robotics). Starting from the data challenges of embodied AI, this talk shares Noitom Robotics' journey from large-scale data factories toward a World … `p-165-from-the-data-factory-to-the-world-compiler`
- 11:45–12:15 **Mastering Embodied Agents: From Large Models to Safe, Reliable Physical Intelligence** — Yu Huang (Researcher, Institute of Advanced Technology, USTC). This talk proposes the Embodied Agentic Harness, a runtime control plane between foundation models and robot skills or hardware. `p-150-具身智能体驾驭-从大模型到安全-可靠的物理智能`
- 14:00–14:35 **Maintaining Dora with Agentic Engineering** — Philipp Oppermann (Freelance Rust Developer). Dora is a Rust-based dataflow framework for robotics and AI, offering low-latency communication across languages. `p-96-maintaining-dora-with-agentic-engineering`
- 14:35–15:10 **Project Homunculus: Open Source Force Feedback Glove for Humanoid Teleoperation** — Martino Russi (Embodied Robotics Engineer, Hugging Face). This talk presents Project Homunculus, a low-cost, open-source force-feedback hand exoskeleton for humanoid teleoperation. `p-49-project-homunculus-open-source-force-feedback-glove-for-humanoid-teleoperation`
- 15:10–15:45 **Nexus: A New Cross-Platform GPU-Based Rust Multiphysics Simulator for Robotics and Training Dataset Generation** — Sébastien Crozet (Founder, Dimforge). Nexus is a cross-platform, GPU-based multiphysics simulator written in Rust for robotics and training-data generation. `p-13-nexus-a-new-cross-platform-gpu-based-rust-multiphysics-simulator-for-robotics-and-training-dataset-generation`
- 16:00–16:30 **From Intelligence to Autonomy: The Case for Homeostatic AI Stress-Gated Control for Embodied Agents in Open-Ended Environments** — Bartłomiej Szejny (Board Member, AI Poland). The talk discusses the need for homeostatic AI stress-gated control to enable embodied agents to operate autonomously while preserving … `p-54-from-intelligence-to-autonomy-the-case-for-homeostatic-ai-stress-gated-control-for-embodied-agents-in-open-ended-environments`
- 16:30–17:00 **Train It or Code It? Let the Robot Decide** — Charbel Dandjinou (Founder & CTO, Reflexion Robotics); Alba María Téllez Fernández (AI Lead, Marso Robotics). At GOSIM Paris, the speaker introduced Skill Foundry, an embodied learning loop enabling AI coding agents to operate across robot software … `p-45-train-it-or-code-it-let-the-robot-decide`
- 17:00–17:30 **From Prediction to Consequence: A New Evaluation Paradigm for Embodied AI** — Alba María Téllez Fernández (AI Lead, Marso Robotics); Charbel Dandjinou (Founder & CTO, Reflexion Robotics). Modern AI excels at predicting actions from offline data, but embodied systems require evaluating how predictions affect real-world … `p-61-from-prediction-to-consequence-a-new-evaluation-paradigm-for-embodied-ai`

### Fri Oct 16 · openGauss Database & Ecosystem Forum · 3F – HAI LIAO
- 14:00–14:35 **Technological Innovation and Practice in the Database Ecosystem in the AI Era** — Zhengzhong Zhou (Council Members of the Database Open Source Development Alliance). Abstract to be announced. `opengauss-database-ecosystem`
- 14:35–15:10 **Breakthroughs in open-source multi-master databases** — Xiaojun Xiong (openGauss System Architect). Abstract to be announced. `opengauss-multi-master`
- 15:10–15:45 **From Vector Databases to the Data Foundation for AI Applications** — Xiaoyu Wang (Architect of CMCC Panwei Database). Abstract to be announced. `opengauss-vector-database`
- 16:00–16:30 **Vastbase: AI Data Foundation for Intelligence-Driven Efficiency** — Lihui Ouyang (Ecosystem Director, South China Region). Abstract to be announced. `opengauss-vastbase`
- 16:30–17:00 **IntarkDB: The Underlying Data Infrastructure for Edge-Side Intelligence** — Zheng Lv (CTO of the Embedded Database Product Department, Greater Bay Area National Technology Innovation Center). Abstract to be announced. `opengauss-intarkdb`
- 17:00–17:30 **Roundtable：Exploring openGauss 7.0.0 LTS Technical Highlights and New Trends in Collaborative Database Ecosystem Development** — Zhengzhong Zhou (Council Members of the Database Open Source Development Alliance); Xiaojun Xiong (openGauss System Architect); Xiaoyu Wang (Architect of CMCC Panwei Database); Lihui Ouyang (Ecosystem Director, South China Region); Zheng Lv (CTO of the Embedded Database Product Department, Greater Bay Area National Technology Innovation Center). Roundtable：Exploring openGauss 7.0.0 LTS Technical Highlights and New Trends in Collaborative Database Ecosystem Development `opengauss-roundtable`

### Sat Oct 17 · AI Education Workshop · 3F – HAI LIAO
- 14:00–14:20 **From Passive Lectures to Active Co-Learning: The AI-Interactive Future Classroom** — Qinlun Qiu (Founder, Boao Open School). Using experience from Boao AI School, this workshop presents an AI-interactive classroom built around a three-stage loop of self-learning … `p-172-from-passive-lectures-to-active-co-learning-the-ai-interactive-future-classroom`
- 14:20–14:40 **Talent Demand in the Field of Embodied AI** — Song Zhao (Co-founder & CEO, Shenlan Academy). This workshop examines the growing demand for people trained across mechanics, electronics, automation … `p-182-具身智能领域人才需求-talent-demand-in-the-field-of-embodied-ai`
- 14:40–15:00 **Full-stage Integrated Practice of Open-source Robots and AI Education** — Zhiqiang Qin (Founder, QTSTEAM). As artificial intelligence evolves rapidly, robotics and AI literacy have become essential parts of young people's innovation skills. `p-194-开源机器人与ai教育的全学段贯通实践`
- 15:00–15:20 **Software Engineering 3.0: Exploration and Practice of Innovative Talent Cultivation Based on Open Source and AI** — Kerry Zhu (Professor, Tongji University). Kerry Zhu explores approaches and practices for cultivating innovative talent through open source and AI in the Software Engineering 3.0 … `p-95-agentos-transforming-autonomous-programming-platforms-into-a-new-type-of-operating-system`
- 15:20–15:40 **Dialogue Is Creation: Reshaping Primary and Secondary School STEM Education with AI Agents** — Maohua Zhou (Deputy Director, Artificial Intelligence Innovation Center, Shenzhen No. 2 Senior High School). Scaling AI literacy and technology education in primary and secondary schools requires enabling every teacher to guide students from an … `p-190-对话即创造-用-ai-智能体重构中小学科技教育`
- 16:00–16:20 **When Confucius Meets Vygotsky — Learning Restructuring and Future School Construction in the AI-Empowered Era** — Yuegang Liu (Vice Principal, Sun Yat-sen University Affiliated School (Shenzhen)). This workshop connects Confucius's individualized teaching with Vygotsky's zone of proximal development to explain how AI can reshape … `p-50-当孔子遇见维果茨基-ai赋能时代的学习重构与未来学校建设`
- 16:20–16:40 **From AI Access to AI Impact: Building Inclusive Education Across Cultures** — Ziyan Wang (Head of Education, NGO UNESCO Avicenne). Ziyan Wang discusses building inclusive education across cultures, moving from access to AI toward its educational impact. `ai-education-inclusive-education`
- 16:40–17:30 **Exploration and Practice of New Global Models for Industry-Academia-Research Education in the AI Era** — Yuegang Liu (Vice Principal, Sun Yat-sen University Affiliated School (Shenzhen)); Yun Lin (Associate Professor, Shanghai Jiao Tong University; Co-Organizer of the Agentic Software Engineering Hackathon); Qinlun Qiu (Founder, Boao Open School); Zhiqiang Qin (Founder, QTSTEAM); Song Zhao (Co-founder & CEO, Shenlan Academy). Moderated by Yuegang Liu, this panel brings together Yun Lin, Qinlun Qiu, Zhiqiang Qin … `ai-education-panel`

### Sat Oct 17 · Agentic AI Summit · 3F – ADEN 1
- 10:15–10:40 **Mapping the Open Agentic AI Landscape: From Open Models to Cross-Foundation Architectures** — Vincent Caldeira (APAC CTO, Red Hat). The talk explores the open agentic AI landscape, emphasizing the need for transparent … `p-84-mapping-the-open-agentic-ai-landscape-from-open-models-to-cross-foundation-architectures`
- 10:40–11:05 **Next-Generation System Interoperability: AI Agents as the Universal Integration Layer** — Katarzyna Starosławska (AI, Data & HPC Expert, LUMI AI Factory / CYFRONET AGH / European Commission). Traditional interoperability methods like APIs and ESBs are struggling with today's dynamic and autonomous systems. `p-30-next-generation-system-interoperability-ai-agents-as-the-universal-integration-layer`
- 11:05–12:00 **Fireside Chat** — David Heinemeier Hansson (DHH) (Creator of Ruby on Rails & Omarchy); Bill Ren (Chief Open Source Liaison Officer of Huawei; Board Member of CNCF). A fireside chat with David Heinemeier Hansson (DHH) and Bill Ren. `summit-fireside-chat`
- 14:00–14:25 **Evaluation You Can Audit: Eclipse PanEval as Shared Infrastructure** — Michael Berns (Head of AI, Eclipse Foundation). This session presents Eclipse PanEval, an open-source framework for auditable evaluation of language and vision models. `p-102-evaluation-you-can-audit-eclipse-paneval-as-shared-infrastructure`
- 14:25–14:50 **Latest LF Research Reports on Agentic AI and AI Coding** — Anni Lai (Generative AI Commons Co-Chair, LF AI & Data). The conference talk presents the latest LF Research reports on Agentic AI and AI coding. `p-52-latest-lf-research-reports-on-agentic-ai-and-ai-coding`
- 14:50–15:15 **Network-Sourced AI: Open Ensembles, Private Data, and a Reproducible Path to the Frontier** — Peter Ide-Kostic (Head of EU Policy, OpenMined Foundation). This talk introduces Network-Sourced AI from the OpenMined Foundation, which combines diverse models in open ensembles. `p-19-network-sourced-ai-open-ensembles-private-data-and-a-reproducible-path-to-the-frontier`
- 15:15–15:40 **Cangjie and the New Frontier of Programming Languages in the AI Era** — Bohua Zhan (Technical Expert, Huawei Programming Language Lab). As software moves toward CPU and LLM co-execution, programming languages must serve both developers and AI agents. `p-107-cangjie-and-the-new-frontier-of-programming-languages-in-the-ai-era`
- 15:40–16:05 **The Agentic AI Developer Economy: Building a Meritocratic Open Source Ecosystem** — Wei Wang (Director, Open Source Technical Committee, Singularity Intelligence Research Institute; Professor, East China Normal University). As artificial intelligence transitions from Generative AI to Agentic AI … `p-117-the-agentic-ai-developer-economy-building-a-meritocratic-open-source-ecosystem`
- 16:05–16:30 **Your AI Product Is Ready. Is Your Company Ready for Europe?** — Kelly Policarpo (Founder & CEO, Lumo AI Compliance & Advisory). Europe is a highly attractive market for AI companies, but entering it requires more than just a great product. `p-29-your-ai-product-is-ready-is-your-company-ready-for-europe`
- 16:30–16:55 **The Sovereignty Layer: Why Open Source Is How the Global South Shapes AI** — Feliana Citradewi (Founder & CEO, Global AI Assembly). The talk discusses how open source can empower the Global South in shaping AI governance. `p-33-the-sovereignty-layer-why-open-source-is-how-the-global-south-shapes-ai`
- 17:20–17:45 **The “Spear and Shield” of Cybersecurity in the AI Era** — Xuewen Gao (Deputy Chief Engineer & Security Architect, QI-ANXIN). Drawing on frontline cybersecurity experience, the speaker explains how AI is reshaping attack chains and presents a practical framework … `p-76-the-spear-and-shield-of-cybersecurity-in-the-ai-era`
- 17:45–18:05 **Hackathon Summary and Awards Ceremony** — Yun Lin (Associate Professor, Shanghai Jiao Tong University; Co-Organizer of the Agentic Software Engineering Hackathon); Zonghuan Wu (Leader, MoFA.AI; Hackathon Co-organizer). Yun Lin and Zonghuan Wu present the hackathon summary and awards. `summit-hackathon-awards`
- 18:05–18:15 **Spotlight Shenzhen 2026: Next-Gen AI-Native Products Awards Ceremony** `summit-spotlight-awards`
- 18:15–18:20 **Closing Ceremony** `summit-closing-ceremony`

### Sat Oct 17 · Agentic AI on Edge · 3F – MING HUA
- 10:15–10:45 **Agentic AI on Global Edge: Deploying SPEAR-Powered Operations Agents with MCP** — Wilson Wang (Software Engineer, ByteDance). ByteDance's global edge infrastructure faces challenges with centralized operations due to latency and fragmented scenarios. `p-4-agentic-ai-on-global-edge-deploying-spear-powered-operations-agents-with-mcp`
- 10:45–11:15 **DHttp: From Partial Connectivity to Omniconnectivity** — Daryl Wong (Co-Founder, GENMETA TECH LIMITED). DHttp addresses the limitations of traditional HTTP by enabling peer-to-peer communication and end-to-end encryption. `p-5-dhttp-from-partial-connectivity-to-omniconnectivity`
- 11:15–11:45 **From Khronos AI Ecosystem Research Insights to Edge AI Inference with Vulkan** — Markus Tavenrath (Principal Engineer, Developer Technology, NVIDIA). As AI and real-time graphics converge, portable AI inference is transitioning from research to real-world deployment. `p-78-from-khronos-ai-ecosystem-research-insights-to-edge-ai-inference-with-vulkan`
- 11:45–12:15 **Which operating system is best for agentic mobile devices?** — Chris Simmonds (Professional Geek, 2net Ltd.). The talk explores alternative operating systems for agentic mobile devices, highlighting Sailfish OS, Ubuntu Touch, and postMarketOS … `p-71-which-operating-system-is-best-for-agentic-mobile-devices`

### Sat Oct 17 · Agentic Device · 2F – KAI XUAN 1
- 10:15–10:50 **Developers' AI Creations: Co-building AI Hardware through the Lens of a Tech Community** — Zhihong Mo (EDA Ecosystem & University Program Lead, JLC Technology Group). AI is moving from the cloud to edge devices and from software to physical entities. `p-53-ai-creations-for-developers-co-building-ai-hardware-from-a-technical-community-perspective`
- 10:50–11:25 **The World as the Interface: Building an Open Agent Ecosystem for AI Glasses** — Weiqi Zhao (Global Head of Open Ecosystem, Rokid). This talk presents a product and ecosystem framework for turning the world into the interface for AI glasses. `p-108-the-world-as-the-interface-building-an-open-agent-ecosystem-for-ai-glasses`
- 11:25–12:00 **Building AI Agent Devices on RISC-V with DC-ROMA Mainboard III** — Yuning Liang (Founder & CEO, DeepComputing); Yanwei Huang (Co-speaker). The talk discusses the use of RISC-V architecture in building AI agent devices … `p-79-building-ai-agent-devices-on-risc-v-with-dc-roma-mainboard-iii`
- 14:00–14:35 **AI-Native Embedded Product Development: Reshaping the Hardware-Software R&D Paradigm** — Yuheng Chen (AI Researcher & Embedded Systems Specialist, ambi). This session shares an AI-native approach to embedded product development that reorganizes software, hardware, tooling … `p-86-ai-原生嵌入式产品研发-重塑软硬件研发范式`
- 14:35–15:10 **Building the Infrastructure for the AI World** — Allen Chao (Director of Sales & Marketing, M5Stack Technology Co., Ltd). This talk introduces M5Stack, explains why its modular hardware ecosystem is useful for rapid product development … `p-161-building-the-infrastructure-for-ai-world`
- 15:10–15:45 **You Built the Prototype. Should It Become a Product?** — Tess Kassier (Fractional GTM & Ecosystem Lead, RiseLink). This talk offers a practical framework for deciding whether an AI-native hardware prototype should become a product. `p-83-you-built-the-prototype-should-it-become-a-product`
- 16:00–16:30 **How Hiwonder Helps Students Apply AI Agents on Robots** — Chun Pak Lee (Overseas Market Strategist, Hiwonder). This talk shows how Hiwonder uses ROS as the contract between an AI agent's reasoning and a robot's actions. `p-163-how-hiwonder-helps-students-apply-ai-agents-on-robots`
- 16:30–17:00 **AI Radar — Industry Transformation Driven by Sensing + Computing** — Hui Zeng (Developer Community Operations Lead, Shenzhen Chengtech Technology Co., Ltd.). As AI moves from the digital world into the physical world, perception is becoming a key bridge between models and real environments. `p-185-ai雷达-感知-计算带来的行业变革`

### Sat Oct 17 · Agentic OS & App · 2F – HAI XIA 2
- 10:15–10:50 **Agent Harness for Multiplayer Collaboration** — Yuchao Qian (Co-founder & CEO, Botiverse). This talk explores Agent Harness design for collaborative environments involving multiple people and multiple AI agents. `p-127-agent-harness-for-multiplayer-collaboration`
- 10:50–11:25 **OctoLoop: Making Agents Truly Loop — Inner-Loop Autonomy, Outer-Loop Correction, and Evolution-Loop Experience Accumulation** — Yue Zhao (Software Engineer, octos Open Source Community). OctoLoop combines an autonomous inner loop with an outer correction loop so coding agents can advance long-running engineering work without … `p-143-hafleet-把-ai-编程助手组织成团队`
- 11:25–12:00 **MemOS: The Next-Generation Memory System for Autonomous Agent Evolution** — Guomian Zhuang (Head of MemOS R&D, Memory Tensor). Guomian Zhuang introduces MemOS as a next-generation memory system for autonomous agent evolution. `p-91-memos-2-0-key-technical-challenges-and-the-evolution-of-memory-systems`
- 14:00–14:35 **Introducing Harness Intelligence Model: JIT-Agent** — Guibin Zhang (PhD Student, National University of Singapore). This talk introduces JIT-Agent, a model that generates task-adaptive agent harnesses on demand for off-the-shelf agentic LLMs. `p-137-introducing-harness-intelligence-model-jit-agent`
- 14:35–15:10 **Voice AI Is Entering Its Second Generation: Lessons from Enterprise Voice Agent Deployments** — Qinying Liao (Principal Program Manager, Microsoft). The talk discusses six key industry shifts transforming Voice AI, including moving from intelligence to execution and from APIs to … `p-31-voice-ai-is-entering-its-second-generation-lessons-from-enterprise-voice-agent-deployments`
- 15:10–15:45 **Agent Harness for Autonomous Server Operations: An End-to-End Approach from Fault Detection to Remediation and Validation** — Xinxin Fan (Maintainer, openUBMC AI SIG, Huawei Technologies Co., Ltd.); Qinghua Li (BMC R&D Engineer, iSoftStone Huafang; Maintainer, openUBMC AI SIG). In BMC firmware development and operations, general-purpose coding agents often lack a deep understanding of the openUBMC technology stack … `p-67-agent-harness-for-autonomous-server-operations-an-end-to-end-approach-from-fault-detection-to-remediation-and-validation`
- 16:00–16:30 **An Autonomous Runtime Shielding Agent for Linux Kernel Vulnerabilities** — Dongbiao He (Associate Professor, Southeast University). This talk presents an autonomous agent for emergency defense against newly disclosed Linux kernel vulnerabilities. `p-133-an-autonomous-runtime-shielding-agent-for-linux-kernel-vulnerabilities`
- 16:30–17:00 **Jiuwen Agent Memory System** — Jingwen Zhao (Technical Expert, Huawei openJiuwen). This talk introduces Jiuwen Agent Memory, a user-centered memory system for personalized, proactive, long-running agents. `p-180-jiuwen-agent-memory记忆系统`
- 17:00–17:30 **From Coding Agents to Autonomous Contributors: Designing the Operating Model for Agentic Software Engineering** — Susanna Wong (Staff AI Engineer, Typeform). This talk examines how coding agents can move beyond individual assistance and become trustworthy contributors to production software … `p-42-from-coding-agents-to-autonomous-contributors-designing-the-operating-model-for-agentic-software-engineering`

### Sat Oct 17 · Google Cloud Workshop · 3F – HAI LIAO
- 10:15–11:15 **Get started with Agent Development Kit (ADK)** — Justin Tan (Solutions Architect, Google Cloud); Jie Wang (Solutions Architect, Google Cloud); Peace He (Solutions Architect, Google Cloud). Begin your journey with the Agent Development Kit (ADK) by building a specialized research assistant. `p-134-get-started-with-agent-development-kit-adk`
- 11:25–12:25 **Build multi-agent systems with ADK** — Justin Tan (Solutions Architect, Google Cloud); Jie Wang (Solutions Architect, Google Cloud); Peace He (Solutions Architect, Google Cloud). Learn to orchestrate complex multi-agent systems using the Agent Development Kit (ADK). `google-cloud-build-multi-agent-systems-with-adk`

### Sat Oct 17 · KVCDN Workshop · 2F – KAI XUAN 2
- 10:15–10:50 **High-Quality Token Service: From Heterogeneous PD to Cross-Region AI Infrastructure** — Hongbo Kang (LLM Systems Architect, Approaching.AI). This workshop explains how Prefill–Decode disaggregation and Mooncake KV-cache handoff allow heterogeneous resource pools to collaborate … `p-140-high-quality-tokens-from-heterogeneous-pd-to-cross-region-ai-infrastructure`
- 10:50–11:25 **LMCache's Production-Grade Multi-Process KV Cache: Architecture, Observability & Fault Tolerance** — Chunxiao Zheng (Core Architect, LMCache). This workshop takes a deep look at LMCache's multi-process architecture and the systems engineering required to make KV-cache management … `p-167-lmcache-s-production-grade-multi-process-kv-cache-architecture-observability-fault-tolerance`
- 11:25–12:00 **KV Cache Usage in SGLang** — Yichi Zhang (Member of Technical Staff, RadixArk). This workshop explains how SGLang uses KV cache from prefix reuse to hierarchical caching. `p-169-kv-cache-usage-in-sglang`
- 14:00–14:35 **UCM: Beyond KVCache Acceleration, Lifecycle Management for Agent-Scale Inference** — Cong Wang (Software Engineer, Huawei Technologies). This workshop examines how agent workloads transform KV-cache reuse, retention, and capacity requirements. `p-132-ucm-beyond-kvcache-acceleration-lifecycle-management-for-agent-scale-inference`
- 14:35–15:10 **Best Practices of Pooling LLM KVCache with FlexKV** — Feiqiang Sun (FlexKV Core Maintainer & Senior Engineer, Tencent Cloud). This workshop explains how FlexKV manages and compresses KV cache across GPU memory, CPU memory, SSDs, and distributed storage. `p-148-聊聊运用-flexkv-进行大模型-kvcache-池化的最佳实践`
- 15:10–15:45 **Research and Practice of Agent Networking** — Cong Li (Deputy Director, Future Network Research Center, China Telecom Research Institute). This workshop explores research and practical work toward an Internet of agents … `p-147-research-and-practice-of-agent-networking`
- 16:00–16:30 **Turbo: Efficiently Serving Long-Context LLMs with In-Network Aggregation** — Ying Wan (Associate Researcher, Southeast University). This workshop presents Turbo, which offloads query multicast and partial-attention aggregation to programmable switches for … `p-141-turbo-efficiently-serving-long-context-llms-with-in-network-aggregation`
- 16:30–17:00 **Beyond Compression Ratio: Service-Aware KV Cache Compression for Distributed LLM Serving** — Zedong Liu (PhD Student, Institute of Computing Technology, Chinese Academy of Sciences). This workshop presents KVServe's service-oriented approach to KV-cache compression … `p-178-beyond-compression-ratio-service-aware-kv-cache-compression-for-distributed-llm-serving`
- 17:00–17:30 **Mooncake Store for Agentic RL in Disaggregated Architectures** — Teng Ma (Maintainer, Mooncake Community). Mooncake primarily provides a high-performance data plane in reinforcement learning (RL): it optimizes rollout data transmission via … `p-186-mooncake-store-for-agentic-rl-in-disaggregated-architectures`

### Sat Oct 17 · Keynote Plenary · 3F – ADEN (full hall)
- 09:10–09:25 **Omarchy: Beautiful, Fun & Agentic Linux** — David Heinemeier Hansson (DHH) (Creator of Ruby on Rails & Omarchy). The age of agents calls for an AI-native operating system. DHH presents Omarchy, a beautiful, fun … `p-123-omarchy-beautiful-fun-agentic-linux`
- 09:25–09:40 **From Open Source Software to Open Intelligence: Silicon Time Is Rewriting the Developer World** — Tao Jiang (Founder & Chairman, CSDN). AI is pushing open source from software collaboration toward intelligence collaboration. `p-124-从开源软件到开源智能-硅基时间正在重写开发者世界`
- 09:40–09:55 **Multimodal Intention Model** — Zhenbo Yu (CEO, NOVA CORE). Nova presents a Multimodal Intention Model (MMIM) for On-Device Deployment. `p-203-multimodel-intension-model`

### Sat Oct 17 · Open Source Models & Infra · 3F – ADEN 2
- 10:15–10:50 **Teaching AI to Improve AI: From Experimental Feedback to Meta-Evolution** — Che Jiang (Ph.D. Candidate & Algorithm Researcher, Tsinghua University / Frontis.AI); Kaiyan Zhang (Co-speaker). Large language models are evolving from coding assistants to research agents capable of proposing solutions, running experiments … `p-100-teaching-ai-to-improve-ai-from-experimental-feedback-to-meta-evolution`
- 10:50–11:25 **Towards Interaction Intelligence** — Xie Zhifei (PhD Researcher, Nanyang Technological University). This talk presents a series of audio-visual interaction research projects from the NUS-LV Lab, spanning affective understanding … `p-149-towards-interaction-intelligence`
- 11:25–12:00 **Title to Be Announced** — Bangxu Yu (CEO, AtomGit). The talk title and abstract will be announced. `p-152-从开源模型到开发者生产力-ai-时代的开源基础设施重构`
- 14:00–14:35 **TransferQueue: An Asynchronous, High-Performance Streaming Data Engine for Post-Training** — Chenghao Rong (Senior Software Engineer, HUAWEI); Yixiang Zhang (Co-speaker); Yongqiang Ma (Open-Source Training Software Expert, Huawei). TransferQueue is an asynchronous, high-performance streaming data engine designed for post-training workflows. `p-60-transferqueue-an-asynchronous-high-performance-streaming-data-engine-for-post-training`
- 14:35–15:10 **Efficient Training of Large Language Models via Orthogonal Transformation** — Weiyang Liu (Assistant Professor, The Chinese University of Hong Kong). This session will explore efficient approaches to large-language-model training based on orthogonal transformation. `p-129-efficient-training-of-large-language-models-via-orthogonal-transformation`
- 15:10–15:45 **C-to-Rust Code Translation: A Three-Stage Curriculum of Pretraining, Debugging-Aware SFT, and Task-Specific SFT** — Yanzhi Wang (Professor, Northeastern University); Pu Zhao (Professor, Southeast University). Translating C code into safe Rust is a key goal for improving software safety. `p-93-c-to-rust-code-translation-a-three-stage-curriculum-of-pretraining-debugging-aware-sft-and-task-specific-sft`
- 16:00–16:30 **Building Self-Improving and Long-Horizon Agents** — Shuyue Hu (Research Scientist, Shanghai AI Lab). Building Self-Improving and Long-Horizon Agents explores how large language models can autonomously enhance their operational systems. `p-99-building-self-improving-and-long-horizon-agents`
- 16:30–17:00 **AI-Ready Data Production and Dynamic Data Training for Open-Source Models** — Meiyi Qiang (Co-Founder, Yuanshu Zhihui). The talk discusses the paradigm shift toward high-quality data dependency for model performance … `p-46-ai-ready-data-production-and-dynamic-data-training-for-open-source-models`
- 17:00–17:30 **Applications of Voice Agents in Embodied Intelligence and High-Quality Data-Driven Solutions** — Jiechen Liu (Director of Ecosystem & Technology, Magic Data). This talk examines how high-quality real-world multimodal data can help voice agents progress from conversation to reliable action in … `p-98-applications-of-voice-agents-in-embodied-intelligence-and-high-quality-data-driven-solutions`

### Sat Oct 17 · Open Source Robotics · 2F – HAI XIA 1
- 10:15–10:45 **"World Model for All": Towards Unified Generation, Navigation and Control** — Yanzhi Wang (Professor, Northeastern University). The talk presents a world model that integrates generation, navigation, and control … `p-94-world-model-for-all-towards-unified-generation-navigation-and-control`
- 10:45–11:15 **Embodied Intelligence VLA Algorithms** — Ning Liu (Algorithm Expert, Beijing Innovation Center of Humanoid Robotics). This talk introduces a VLA algorithm for embodied intelligence. Further details will be published as the session content is confirmed. `p-101-vla`
- 11:15–11:45 **Everyone Can Build an Open-Source Robot** — Jennie Wang (AI Robotics Product Marketing, Seeed Studio). We still don’t know what the most successful robots of the future will look like — a humanoid, a robotic arm, a mobile manipulator … `p-193-everyone-can-build-an-open-source-robot`
- 11:45–12:15 **From Leaderboards to Global Infrastructure: Building an Open Evaluation Ecosystem for Embodied AI** — Emily Chen (Co-founder, RoboChallenge). This talk traces RoboChallenge's evolution from real-robot benchmarks and global leaderboards toward neutral … `p-130-from-leaderboards-to-global-infrastructure-building-an-open-evaluation-ecosystem-for-embodied-ai`
- 14:00–14:35 **From Single-Robot Intelligence to Multi-Agent Coordination: The Evolution of AIRSEAI** — Liuwang Kang (Associate Researcher, Shenzhen Institute of Artificial Intelligence and Robotics for Society); Hongjun Zhou (Associate Researcher, Shenzhen Institute of Artificial Intelligence and Robotics for Society). The talk discusses the evolution of AIRSEAI from single-robot intelligence to multi-agent coordination, highlighting its modular pipeline … `p-16-from-single-robot-intelligence-to-multi-agent-coordination-the-evolution-of-airseai`
- 14:35–15:10 **Rethinking Efficiency Bottleneck of Generative Robotics Manipulation** — Zhenghao Chen (Assistant Professor, University of Newcastle). This talk examines two major barriers to deploying generative embodied AI on real robots: redundant multi-view sensory data and the … `p-136-rethinking-efficiency-bottleneck-of-generative-robotics-manipulation`
- 15:10–15:45 **Interactive Heuristic Learning Method of LiDAR and Camera for Target Detection** — Cen Ming (Professor, Chongqing University of Posts and Telecommunications). This talk proposes an interactive heuristic learning method that combines LiDAR and camera data for target detection on intelligent mobile … `p-103-interactive-heuristic-learning-method-of-lidar-and-camera-for-target-detection`
- 16:00–16:30 **AMD ROCm and Radeon-Powered Real2Sim2Real Vision-Language-Action Manipulation** — Charles Yang (AI Solution Architect, AMD). AMD ROCm and Radeon GPUs enable an end-to-end Real2Sim2Real workflow for embodied AI, covering data generation, policy training … `p-2-amd-rocm-and-radeon-powered-real2sim2real-vision-language-action-manipulation`
- 16:30–17:00 **PhyAgentOS: Recursively Self-Evolving Physical Agent Operating System** — Tao Pu (R&D Director, X-Era Lab). This talk shares PhyAgentOS engineering practices for physical-agent harnesses, including unified access to heterogeneous robots … `p-158-phyagentos-递归自进化物理智能体操作系统`
- 17:00–17:30 **Full-Stack Embodied AI OS — Introduction to openEuler Intelligence Boom Robot (IB-Robot)** — Xin Chen (Engineer, Huawei Technologies). IB-Robot is a full-stack embodied AI OS developed by the OpenAtom openEuler community … `p-63-full-stack-embodied-ai-os-introducing-openeuler-intelligence-boom-robot-ib-robot`

### Sat Oct 17 · vLLM Workshop · 3F – MING HUA
- 13:40–13:50 **Opening Remarks** — Hongsheng Liu (vLLM-Omni Core Maintainer, Chief Architect of InferMatrix Project); Chuhui Chen (Principal Architect, Red Hat). Opening remarks by Hongsheng Liu and Chuhui Chen. `vllm-opening-remarks`
- 13:50–14:20 **vLLM Latest Update and Roadmap** — Jiangyun Zhu (Engineer at Inferact, vLLM Core Maintainer). Jiangyun Zhu presents the latest vLLM features and the project roadmap. `vllm-latest-update-roadmap`
- 14:20–14:50 **llm-d: Building a Cross-Workload, Cross-Modal, Cross-Hardware, and Cross-Platform Distributed Inference Control Plane** — Chuhui Chen (Principal Architect, Red Hat). This talk introduces llm-d's distributed inference control plane, including intelligent routing, endpoint selection, inference pools … `p-159-llm-d-打造跨负载-跨模态-跨硬件-跨平台的分布式推理平面`
- 14:50–15:20 **AFD Plugin: Attention–FFN Disaggregation in vLLM** — Chenzhou Jiang (vLLM AFD-Plugin Core Maintainer, Engineer at Huawei). This workshop introduces AFD Plugin, an external vLLM plugin that separates Attention and FFN or MoE execution into independently … `p-170-afd-plugin-attention-ffn-disaggregation-in-vllm`
- 15:40–16:10 **From Single-Point Acceleration to System-Wide Optimization: Full-Stack Optimization Practices for LLM Inference** — Donghua Jiang (Senior Inference Engineer, Tencent Hunyuan Team). Drawing on Hunyuan inference and GPU engineering experience, this workshop presents a service-goal-oriented method for LLM optimization. `p-171-从单点加速到系统最优-大模型推理的全栈优化实践`
- 16:10–16:40 **Inside ROCm 10.0: Building an Open GPU Software Platform for the Agentic AI Era** — Wei Cai (Product Application Engineer, AMD). This workshop explores ROCm 10.0 from GPU drivers, runtimes, compilers, and optimized libraries to AI frameworks. `p-177-inside-rocm-10-building-an-open-gpu-software-platform-for-the-agentic-ai-era`
- 16:40–17:10 **Scaling vLLM System-Wide: From Network I/O to Distributed Scheduling** — Zhenwei Pi (Founder, Tensorfer). This workshop presents deep vLLM optimizations for cold-start latency, KV-cache efficiency, and distributed scheduling. `p-126-scaling-vllm-system-wide-from-network-i-o-to-distributed-scheduling`
- 17:10–17:30 **AMA with the vLLM Core Team** `vllm-core-team-ama`

## GOSIM speakers (name · role · links) — speaker page: /speakers/<id>/
- **David Heinemeier Hansson (DHH)** `dhh` · Creator of Ruby on Rails & Omarchy · https://dhh.dk/ https://x.com/dhh https://github.com/dhh
- **Rik Arends** `rik-arends` · Co-Founder, Makepad · https://makepad.nl/ https://github.com/makepad/makepad https://x.com/rikarends https://www.linkedin.com/in/arendsrik/
- **Michael Berns** `michael-berns` · Head of AI, Eclipse Foundation · https://www.linkedin.com/in/aithoughtleader
- **Fu Bingyang** `bingyang-fu` · Triton Operator Technical Expert, Huawei
- **Hunter Bown** `hunter-bown` · Founder, ShannonTek · https://shannontek.com/ https://github.com/hmbown/ https://x.com/goodhunt https://www.linkedin.com/in/hunterbown/
- **Birgitta Böckeler** `birgitta-boeckeler` · Distinguished Engineer · https://birgitta.info/ https://www.linkedin.com/in/birgittaboeckeler/
- **Wei Cai** `wei-cai` · Product Application Engineer, AMD · https://github.com/Vivicai1005 https://www.linkedin.com/in/wei-cai-1005
- **Vincent Caldeira** `vincent-caldeira` · APAC CTO, Red Hat · https://thinkinginsidethebox.ai/ https://www.linkedin.com/in/caldeirav/
- **Allen Chao** `allen-chao` · Director of Sales & Marketing, M5Stack Technology Co., Ltd · Director of Sales and Marketing at M5Stack. He is a technology enthusiast and football fan with a curiosity for new … · https://www.m5stack.com/ https://www.linkedin.com/in/allen-chao-68401275
- **An Chen** `an-chen` · Co-founder, Chairman & CEO, Shenzhen Zhiweitong Technology
- **Haibo Chen** `chen-haibo` · Chair, OpenHarmony Technical Steering Committee
- **Xin Chen** `chen-xin` · Engineer, Huawei Technologies · A maintainer of the openEuler Embedded SIG with long-term experience in embedded real-time operating systems …
- **Chuhui Chen** `chuhui-chen` · Principal Architect, Red Hat
- **Emily Chen** `emily-chen` · Co-founder, RoboChallenge · General Manager of Open Source Strategy & Ecosystem at Dexmal …
- **Jianjun Chen** `jianjun-chen` · ops-transformer Committer
- **Qiuji Chen** `qiuji-chen` · Graduate Student, Chongqing University of Posts and Telecommunications
- **Siheng Chen** `siheng-chen` · Engineer, Second State
- **Yuheng Chen** `yuheng-chen` · AI Researcher & Embedded Systems Specialist, ambi · A serial entrepreneur, AI researcher, and embedded-systems specialist at ambi. · https://github.com/Adancurusul
- **Zhenghao Chen** `zhenghao-chen` · Assistant Professor, University of Newcastle
- **Feliana Citradewi** `feliana-citradewi` · Founder & CEO, Global AI Assembly · The Founder and CEO of Global AI Assembly. · https://globalaiassembly.com/ https://www.linkedin.com/in/feliana-citradewi%F0%9F%8E%99%EF%B8%8F-39657a83
- **Wayne Connolly** `wayne-connolly` · COO, FuriLabs · A co-presenter of “Agentic AI as a Contributor to Mobile Linux” at GOSIM Shenzhen 2026.
- **Sébastien Crozet** `sebastien-crozet` · Founder, Dimforge · https://dimforge.com/ https://github.com/dimforge
- **Tristan Ruoli Dai** `tristan-ruoli-dai` · Founder/CEO, Noitom Robotics · Dr. Ruoli Dai, founder of Noitom Robotics and co-founder of Noitom Ltd., focuses on human motion digitization … · https://modalitynet.com/ https://github.com/noitom-robotics https://www.linkedin.com/in/tristan-ruoli-dai-b2369330/
- **Charbel Dandjinou** `charbel-dandjinou` · Founder & CTO, Reflexion Robotics · The founder and CTO of Reflexion Robotics, a Paris-based startup building A OS, a safety runtime for embodied AI. · https://www.cd-ia.blog/
- **Pieter Delobelle** `pieter-delobelle` · Co-speaker · A co-presenter of “SynthCommonCorpus: The Largest Open Synthetic Pretraining Corpus Built for Agentic Models” at GOSIM …
- **Tian Ding** `tian-ding` · Founder, Zhizi Xinyuan
- **Sean Dong** `sean-dong` · Program Director, Huawei Programming Language Lab
- **Chao Du** `chao-du` · openvela Project Lead, Xiaomi · Chao Du leads the openvela open-source project at Xiaomi. He has more than a decade of experience in open-source and …
- **Frank Fan** `frank-fan` · Principal Solutions Architect, AWS · A Principal Container Solutions Architect at AWS in Australia … · https://github.com/quickzebra https://www.linkedin.com/in/frankfan7/
- **Xinxin Fan** `xinxin-fan` · Maintainer, openUBMC AI SIG, Huawei Technologies Co., Ltd.
- **Xiaodong Feng** `xiaodong-feng` · Head of the Physical AI Product Line, Agora · A graduate of Harbin Institute of Technology, Xiaodong Feng currently leads Physical AI products at Agora.
- **Alba María Téllez Fernández** `alba-maria-tellez-fernandez` · AI Lead, Marso Robotics · https://amtellezfernandez.com/ https://github.com/amtellezfernandez https://x.com/leader_arm https://linkedin.com/in/amtellezfernandez
- **Tingsheng Fu** `fu-tingsheng` · Senior Vice President, AsiaInfo Security
- **Xuewen Gao** `xuewen-gao` · Deputy Chief Engineer & Security Architect, QI-ANXIN
- **Sunny Gao** `高阳-sunny` · Founder & CEO, MindMux.ai · The founder and CEO of MindFly Lab (MindMux.ai), where he is building a persistent context layer for AI-native teams — … · https://sunnygao.com https://github.com/sunshineg https://x.com/sunnyygao https://www.linkedin.com/in/sunnygao
- **Keshu Han** `keshu-han` · Embodied AI Developer, Beijing Dora Intelligence
- **Dongbiao He** `dongbiao-he` · Associate Professor, Southeast University · A co-presenter of “An Autonomous Runtime Shielding Agent for Linux Kernel Vulnerabilities” at GOSIM Shenzhen 2026.
- **Peace He** `peace-he` · Solutions Architect, Google Cloud
- **Jacky Hsu** `jacky-hsu` · Founder & CEO, Ingora · The Founder of Ingora, an AI-native learning companion company building next-generation AI companion devices for … · https://ingora.ai/ https://github.com/Ingora-Inc/Qrio https://www.linkedin.com/in/jacky-hsu-7ba6341/
- **Shuyue Hu** `shuyue-hu` · Research Scientist, Shanghai AI Lab
- **Jia Huang** `jia-huang-黄佳` · Chief Technical Consultant, Singularity Intelligence Research Institute · Lead AI Engineer at A*STAR Singapore, and a technical author who writes about how AI agents are engineered. · https://kage-ai.com/ https://github.com/huangjia2019 https://www.linkedin.com/in/jia-huang-adps/
- **Yanwei Huang** `yanwei-huang` · Co-speaker · A co-presenter of “Building AI Agent Devices on RISC-V with DC-ROMA Mainboard III” at GOSIM Shenzhen 2026.
- **Yu Huang** `yu-huang` · Researcher, Institute of Advanced Technology, USTC
- **Peter Ide-Kostic** `peter-ide-kostic` · Head of EU Policy, OpenMined Foundation · https://openmined.org/ https://github.com/openmined https://x.com/openminedorg https://linkedin.com/in/peter-ide-kostic-52ab988
- **Che Jiang** `che-jiang` · Ph.D. Candidate & Algorithm Researcher, Tsinghua University / Frontis.AI · A Ph.D. candidate at Tsinghua University and an Algorithm Researcher at Frontis.AI.
- **Chenzhou Jiang** `chenzhou-jiang` · vLLM AFD-Plugin Core Maintainer, Engineer at Huawei · An AI Infrastructure Engineer at Huawei and a core maintainer of the afd-plugin repository in the vLLM community.
- **Tao Jiang** `jiang-tao` · Founder & Chairman, CSDN · The founder and chairman of CSDN and the initiator of GOSIM. Across more than 30 years in software, the internet …
- **Donghua Jiang** `landojiang` · Senior Inference Engineer, Tencent Hunyuan Team
- **Willem Jiang** `willem-jiang` · Chief Technical Consultant, Singularity Intelligence Research Institute; AI Agent Expert · An independent open-source and agentic AI consultant and a core contributor to DeerFlow. · https://willemjiang.github.io/ https://x.com/willemjiang https://www.linkedin.com/in/jiangning
- **Fahua Jin** `fahua-jin` · Co-Founder & CTO, EMQ · Co-Founder and CTO of EMQ, where he leads product and R&D. He has initiated and contributed to multiple open-source …
- **Cenzhe Chase Jing** `chenzhe-jing` · Head of Open Source Ecosystem, ModelBest · Chenzhe Jing leads the open-source ecosystem at ModelBest and supports the company's Chief Scientist.
- **Hongbo Kang** `hongbo-kang` · LLM Systems Architect, Approaching.AI · An architect at Approaching.AI and holds a Ph.D. in Computer Science from Tsinghua University.
- **Liuwang Kang** `liuwang-kang` · Associate Researcher, Shenzhen Institute of Artificial Intelligence and Robotics for Society · Shenzhen Institute of Artificial Intelligence and Robotics for Society
- **Tess Kassier** `tess-kassier` · Fractional GTM & Ecosystem Lead, RiseLink · A Yale Ventures Entrepreneur-in-Residence, founder, and fractional go-to-market and ecosystem lead at RiseLink … · https://www.linkedin.com/in/tessmaggio/
- **Minako Kojima** `minakokojima` · Head of Developer Relations, Moonshot AI · https://github.com/lychees https://x.com/MinakoOikawa
- **Anni Lai** `anni-lai` · Generative AI Commons Co-Chair, LF AI & Data
- **Hsuan Han Lai** `hsuan-han-lai` · Lead of Developer Ecosystem, Tuya Smart Inc · Hsuan Han Lai leads the developer ecosystem at Tuya Smart and is the technical lead of TuyaOpen and an architect of the … · https://tuyaopen.ai/ https://github.com/adwuard http://linkedin.com/in/hsuan-han-l-37782b92
- **Chun Pak Lee** `lee-chun-pak` · Overseas Market Strategist, Hiwonder · https://www.linkedin.com/in/leechunpak/
- **Cong Li** `cong-li` · Deputy Director, Future Network Research Center, China Telecom Research Institute
- **Jianzhong Li** `jianzhong-li` · President, Singularity Intelligence Research Institute / Senior Vice President, CSDN · https://singintelligence.com/ https://linkedin.com/in/jianzhongli
- **Peilin Li** `peilin-li` · Ph.D. Student, Tsinghua University / Approaching AI · https://github.com/JimmyPeilinLi
- **Qinghua Li** `qinghua-li` · BMC R&D Engineer, iSoftStone Huafang; Maintainer, openUBMC AI SIG
- **Yang Li** `yang-li` · Technical Lead, DORA Community · https://doracc.com/ https://github.com/doracn
- **Yuning Liang** `yuning-liang` · Founder & CEO, DeepComputing · The founder and CEO of DeepComputing, which develops RISC-V products including laptops, tablets, workstations … · https://deepcomputing.io/ https://x.com/Yuning_XC5 https://www.linkedin.com/in/yuningliang/
- **Qinying Liao** `qinying-liao` · Principal Program Manager, Microsoft · Senior AI Product Leader with 10+ years at Microsoft Azure AI, specializing in Speech AI and Voice Agents. · https://www.linkedin.com/in/qinying-liao-7458b358/
- **Jiahang Lin** `jiahang-lin` · Master's Student, Fudan University · A master’s student at Fudan University’s FudanNLP Lab, co-advised by Tao Gui and Xuanjing Huang. · https://curry09.github.io/ https://github.com/Curry09
- **Yun Lin** `yun-lin` · Associate Professor, Shanghai Jiao Tong University; Co-Organizer of the Agentic Software Engineering Hackathon · Shanghai Jiao Tong University; Co-Organizer of the Agentic Software Engineering Hackathon
- **Tong Ling** `tong-ling` · Head of IoT Product Commercialization, Espressif Systems · Tong Ling leads IoT product commercialization at Espressif Systems …
- **Wu Lingfei** `lingfei-wu` · AscendNPU IR Technical Expert, Huawei Compiler Lab
- **Hongsheng Liu** `hongsheng-liu` · vLLM-Omni Core Maintainer, Chief Architect of InferMatrix Project · A core maintainer of vLLM-Omni and Chief Architect of the InferMatrix Project.
- **Jiechen Liu** `jiechen-liu` · Director of Ecosystem & Technology, Magic Data
- **Ning Liu** `ning-liu` · Algorithm Expert, Beijing Innovation Center of Humanoid Robotics · Ning Liu earned his Ph.D. from Northeastern University in the United States.
- **Shiwei Liu** `shiwei-liu` · Group Leader, Max Planck Institute for Intelligent Systems / ELLIS Institute Tübingen · Max Planck Institute for Intelligent Systems / ELLIS Institute Tübingen · https://shiweiliuiiiiiii.github.io/ https://x.com/Shiwei_Liu66 https://www.linkedin.com/in/shiwei-liu-3b60771ab/
- **Weiyang Liu** `weiyang-liu` · Assistant Professor, The Chinese University of Hong Kong
- **Yuegang Liu** `yuegang-liu` · Vice Principal, Sun Yat-sen University Affiliated School (Shenzhen)
- **Zedong Liu** `zedong-liu` · PhD Student, Institute of Computing Technology, Chinese Academy of Sciences · https://zedong-liu.github.io/ https://github.com/Zedong-Liu
- **Zixi Liu** `zixi-liu` · Senior Engineer, Huawei · Zixi Liu holds a Ph.D. from Nanjing University and works at Huawei's Programming Languages Laboratory in the 2012 …
- **Zheng Lv** `zheng-lv` · CTO of the Embedded Database Product Department, Greater Bay Area National Technology Innovation Center
- **Yongqiang Ma** `codingma` · Open-Source Training Software Expert, Huawei · CodingMa holds a master's degree from Peking University and has worked extensively on training systems for NLP and … · https://github.com/codemayq
- **Teng Ma** `teng-ma` · Maintainer, Mooncake Community · Teng Ma received my Ph.D. from Tsinghua University in 2021. He builds innovative software systems exploiting new … · https://stmatengss.github.io/ https://github.com/stmatengss https://x.com/TengMa3577
- **Satya Mallick** `satya-mallick` · CEO, OpenCV.org · https://learnopencv.com/ https://github.com/spmallick/learnopencv https://x.com/LearnOpenCV https://www.linkedin.com/in/satyamallick/
- **Cen Ming** `cen-ming` · Professor, Chongqing University of Posts and Telecommunications
- **Zhihong Mo** `zhihong-mo` · EDA Ecosystem & University Program Lead, JLC Technology Group · The higher-education manager and ecosystem platform lead at JLC Technology Group … · https://oshwhub.com/
- **Bardia Moshiri** `bardia-moshiri` · Embedded Software Engineer, Furi Labs · https://github.com/fakeshell https://www.linkedin.com/in/bardia-moshiri/
- **Iaroslav Neverov** `iaroslav-neverov` · Full-stack Engineer, Pleias
- **Philipp Oppermann** `philipp-oppermann` · Freelance Rust Developer · https://os.phil-opp.com/
- **Lihui Ouyang** `lihui-ouyang` · Ecosystem Director, South China Region
- **Zhenwei Pi** `zhenwei-pi` · Founder, Tensorfer
- **Kelly Policarpo** `kelly-policarpo` · Founder & CEO, Lumo AI Compliance & Advisory · The founder of Lumo AI Compliance & Advisory and specializes in AI governance and entry into the European market. · https://www.lumoai.pt/ https://x.com/policarpolumoai
- **Tao Pu** `tao-pu` · R&D Director, X-Era Lab · https://putao537.github.io/ https://github.com/putao537
- **Yuchao Qian** `yuchao-qian` · Co-founder & CEO, Botiverse · The co-founder of Raft.build, a multiplayer, multi-agent collaboration platform. · https://stdrc.cc/ https://github.com/stdrc https://x.com/istdrc https://www.linkedin.com/in/stdrc/
- **Meiyi Qiang** `meiyi-qiang` · Co-Founder, Yuanshu Zhihui · https://github.com/Qmeiyi
- **Zhiqiang Qin** `秦志强` · Founder, QTSTEAM
- **Qinlun Qiu** `qiuqinlun` · Founder, Boao Open School · An industry–education collaboration specialist with nearly 30 years of experience in IT education.
- **Bill Ren** `xudong-ren` · Chief Open Source Liaison Officer of Huawei; Board Member of CNCF
- **Chenghao Rong** `chenghao-rong` · Senior Software Engineer, HUAWEI · Chenghao Rong graduated from Tsinghua University. He joined Huawei in 2024 …
- **Yi Ru** `yi-ru` · Founder & CEO, Lawaken Technology · The founder and CEO of Lawaken Technology and a veteran smart-hardware entrepreneur with more than 20 years of …
- **Martino Russi** `martino-russi` · Embodied Robotics Engineer, Hugging Face · Aspiring mad scientist, trying to create this generation's Pinocchio. · https://github.com/nepyope https://x.com/NepYope https://www.linkedin.com/in/martino-russi/
- **Igor Schwarzmann** `igor-schwarzmann` · Principal, Known Unknowns GmbH · https://igorschwarzmann.com/ https://github.com/igor https://www.linkedin.com/in/igorschwarzmann/
- **Lixin Shao** `lixin-shao` · General Manager of CANN business, Huawei
- **Chris Simmonds** `chris-simmonds` · Professional Geek, 2net Ltd. · https://2net.co.uk/ https://github.com/csimmonds https://uk.linkedin.com/in/chrisdsimmonds/
- **Mehdi Snene** `mehdi-snene` · Chief AI Officer, Digital infrastructure and emerging technologies, UN
- **Tiberiu Socaci** `tiberiu-socaci` · CEO & Co-Founder, Makeitfuture · https://www.selfevolving.app/ https://www.linkedin.com/in/tiberiusocaci/
- **Katarzyna Starosławska** `katarzyna-starosławska` · AI, Data & HPC Expert, LUMI AI Factory / CYFRONET AGH / European Commission · https://www.linkedin.com/in/kstaroslawska/
- **Anastasia Stasenko** `anastasia-stasenko` · Co-Founder & CEO, Pleias · Co-Founder and CEO of Pleias, a Franco-German lab developing data infrastructure for frontier AI systems. · https://substack.com/@anastasiastasenko https://www.linkedin.com/in/anastasia-stasenko/
- **Feiqiang Sun** `feiqiang-sun` · FlexKV Core Maintainer & Senior Engineer, Tencent Cloud · A Senior Engineer at Tencent Cloud with nine years of cloud-computing R&D experience. · https://github.com/feiqiangs https://www.linkedin.com/in/feiqiang-sun-5aa2951b0/
- **Yujie Sun** `yujie-sun` · R&D Engineer, Daorui Intelligent Technology (Beijing) Co., Ltd.
- **Bartłomiej Szejny** `bartlomiej-szejny` · Board Member, AI Poland · https://aipoland.org/ https://www.linkedin.com/in/bartlomiej-szejny-9627b051/
- **Justin Tan** `xin-tan` · Solutions Architect, Google Cloud
- **Qiyang Tan** `谭棋洋` · Dev, Dora
- **Canran Tang** `canran-tang` · Graduate Student, University of Science and Technology of China · https://github.com/tang-canran
- **Markus Tavenrath** `markus-tavenrath` · Principal Engineer, Developer Technology, NVIDIA · https://www.linkedin.com/in/markus-tavenrath/
- **Gregory Terzian** `gregory-terzian` · Founder, FOSS (Shanghai) Technology Consulting · https://github.com/gterzian
- **Frey Tian** `frey-tian` · Huawei Ascend Computing Inference Technology Expert, Huawei
- **Slava Tykhonov** `slava-tykhonov` · Head of AI & Interoperability, CODATA · Head of AI and Interoperability at CODATA. With over 25 years’ experience in software development, data science … · https://github.com/4tikhonov https://x.com/4tykhonov https://www.linkedin.com/in/vyacheslavtikhonov/
- **Ying Wan** `wan-ying` · Associate Researcher, Southeast University
- **Baofeng Wang** `baofeng-wang` · Co-founder, Shanghai Mood Perception Intelligence Technology
- **Cong Wang** `cong-wang` · Software Engineer, Huawei Technologies
- **Jennie Wang** `jennie-wang` · AI Robotics Product Marketing, Seeed Studio · Dive into the Physical AI ecosystem at Seeed Studio, particularly in product marketing and partnership/dev community … · https://www.seeedstudio.com/blog/author/jennie-wang/
- **Jie Wang** `jie-wang` · Solutions Architect, Google Cloud
- **Claudia Wang** `rin` · Senior Algorithm Engineer, Moeru AI Ltd.
- **Wei Wang** `wei-wang-王伟` · Director, Open Source Technical Committee, Singularity Intelligence Research Institute; Professor, East China Normal University
- **Wilson Wang** `wilson-wang` · Software Engineer, ByteDance · https://github.com/wilsonwang371 https://www.linkedin.com/in/wilson-wang/
- **Xiaoyu Wang** `xiaoyu-wang` · Architect of CMCC Panwei Database
- **Yanzhi Wang** `yanzhi-wang` · Professor, Northeastern University
- **Ziyan Wang** `ziyan-wang` · Head of Education, NGO UNESCO Avicenne
- **Yongcheng Wei** `yongcheng-wei` · PhD Student, Chongqing University of Posts and Telecommunications
- **Daryl Wong** `daryl-wong` · Co-Founder, GENMETA TECH LIMITED · https://www.dhttp.net https://github.com/genmeta
- **Susanna Wong** `susanna-wong` · Staff AI Engineer, Typeform · https://github.com/studioswong?tab=overview&from=2026-03-01&to=2026-03-31 https://x.com/studioswong https://www.linkedin.com/in/susanna-wong-london/
- **Zonghuan Wu** `zonghuan-wu` · Leader, MoFA.AI; Hackathon Co-organizer
- **Wencheng Xiao** `wencheng-xiao` · PhD Candidate, Shijiazhuang Tiedao University
- **Weiyu Xie** `weiyu-xie` · Chief Architect, Approaching.AI · https://github.com/ErvinXie
- **Xiaojun Xiong** `xiaojun-xiong` · openGauss System Architect
- **Zhiqiang Xiong** `zhiqiang-xiong` · ops-transformer Committer
- **Wang Yajun** `yajun-wang` · Kunpeng AI Agent Technical Expert
- **Charles Yang** `charles-yang` · AI Solution Architect, AMD · A core technical instructor for Agentic AI and Physical AI at AMD China and an architect focused on AI ecosystem … · https://github.com/charyang-ai https://www.linkedin.com/in/charles-yang-2162b269
- **Liyun Yang** `liyun-yang` · Director, Open Source Research Office, China Electronics Standardization Institute · Over ten‑year track record in leading China’s cloud computing standardization …
- **Yujie Yang** `yujie-yang` · Co-speaker · A co-presenter of “KTransformers: The Fine-Tuning-to-Inference Closed Loop for Full-Precision 1T-Class MoE Models on …
- **Zhenyu Yang** `杨振宇` · Founder and CEO, Shenzhen Ciyuan Kaiwu Technology Co., Ltd.
- **Bangxu Yu** `bangxu-yu` · CEO, AtomGit
- **Zhenbo Yu** `zhenboyu` · CEO, NOVA CORE · In the first cohort of the Wu Wenjun Artificial Intelligence Honorary Doctoral Program at Shanghai Jiao Tong University …
- **Michael Yuan** `michael-yuan` · Founder of Second State & Co-Founder of GOSIM · A founder, investor, and agentic engineer focused on open-source AI and Rust. · https://github.com/juntao https://x.com/juntao https://linkedin.com/in/myuan
- **Yuu** `yuu` · Agent Performance & Optimization Intern, Dify · Yuu, also known as tommy0103, is the author of Obelisk, an open-source evidence layer that unifies coding-agent session … · https://obelisk.antinomie.org/ https://x.com/QuantumTransf
- **Hui Zeng** `曾辉` · Developer Community Operations Lead, Shenzhen Chengtech Technology Co., Ltd. · https://github.com/Niko-Zeng https://www.linkedin.com/in/niko-zeng/
- **Bohua Zhan** `bohua-zhan` · Technical Expert, Huawei Programming Language Lab
- **Fanshi Zhang** `fanshi-zhang` · CTO, Moeru AI · http://nolebase.ayaka.io/ https://x.com/ayakaneko https://www.linkedin.com/in/fanshi-zhang-851980271
- **Guibin Zhang** `guibin-zhang` · PhD Student, National University of Singapore · A Ph.D. student in the School of Computing at the National University of Singapore. · https://guibinz.top/
- **Haibin Zhang** `haibin-zhang` · AI Infrastructure & Open Source Lead, Dexmal · Haibin Zhang leads AI infrastructure and the OpenDM and Dexbotic open-source projects at Dexmal. · https://github.com/dexmal/OpenDM
- **Jiahui Zhang** `jiahun-zhang` · Expert, Huawei · A Jiuwen Symbiosis SIG Maintainer. He has long focused on building Physical AI Agent capabilities and is responsible …
- **Kaiyan Zhang** `kaiyan-zhang` · Co-speaker · A co-presenter of “Teaching AI to Improve AI: From Experimental Feedback to Meta-Evolution” at GOSIM Shenzhen 2026.
- **Quanshi Zhang** `quanshi-zhang` · Associate Professor, Shanghai Jiao Tong University
- **Yichi Zhang** `yichi-zhang` · Member of Technical Staff, RadixArk · An SGLang developer focused on efficient LLM inference, with an interest in KV cache management and optimization. · https://yichizhang.dev/ https://github.com/Ccyest https://x.com/YichiZ03 https://www.linkedin.com/in/yichi-zhang2003/
- **Yixiang Zhang** `yixiang-zhang` · Co-speaker · A co-presenter of “TransferQueue: An Asynchronous, High-Performance Streaming Data Engine for Post-Training” at GOSIM …
- **Yuchen Zhang** `yuchen-zhang` · TileLang-Ascend Community Collaborator
- **Yuxuan Zhang** `yuxuan-zhang` · Technology Evangelist, Zhipu AI · https://github.com/zRzRzRzRzRzRzR https://x.com/zRdianjiao https://www.linkedin.com/in/yuxuan-zhang-86a124282/
- **Weiqi Zhao** `weiqi-zhao` · Global Head of Open Ecosystem, Rokid · Weiqi Zhao leads Rokid's global developer and partner ecosystem for AI and AR glasses. · https://www.linkedin.com/in/weiqizhao/
- **Song Zhao** `zhao-song` · Co-founder & CEO, Shenlan Academy · Co-founder and CEO of Shenlan Academy. He holds a master's degree from the Institute of Automation … · https://www.shenlanxueyuan.com/
- **Zhongxia Zhao** `赵仲夏` · Co-Founder & COO, EvoPhys AI · Co-Founder and COO of EvoPhys AI. He holds a master’s degree from Peking University and previously served as a …
- **Yue Zhao** `赵悦-zhao-yue` · Software Engineer, octos Open Source Community
- **Pu Zhao** `赵普` · Professor, Southeast University
- **Jingwen Zhao** `赵靖文` · Technical Expert, Huawei openJiuwen
- **Chunxiao Zheng** `chunxiaozheng` · Core Architect, LMCache
- **Jiaqi Zheng** `jiaqi-zheng` · Associate Professor, Nanjing University · https://jzheng369.github.io/index.html https://github.com/jzheng369
- **Yaowei Zheng** `yaowei-zheng` · Co-Founder & CTO, PrismShadow · Co-Founder and CTO of PrismShadow and a Ph.D. student in computer science at Beihang University. · https://github.com/hiyouga https://x.com/code_hiyouga https://www.linkedin.com/in/hiyouga/
- **Xie Zhifei** `zhifei-xie` · PhD Researcher, Nanyang Technological University
- **Feynman Zhou** `feynman-zhou` · CNCF Ambassador，Senior Product Manager for Tencent Cloud
- **Hongjun Zhou** `hongjun-zhou` · Associate Researcher, Shenzhen Institute of Artificial Intelligence and Robotics for Society · Shenzhen Institute of Artificial Intelligence and Robotics for Society
- **Zhengzhong Zhou** `zhengzhong-zhou` · Council Members of the Database Open Source Development Alliance
- **Maohua Zhou** `周茂华` · Deputy Director, Artificial Intelligence Innovation Center, Shenzhen No. 2 Senior High School
- **Jiangyun Zhu** `jiangyun-zhu` · Engineer at Inferact, vLLM Core Maintainer
- **Kerry Zhu** `kerry-zhu` · Professor, Tongji University · https://blog.csdn.net/kerryzhu https://github.com/kerryzhu https://x.com/Kerryzhu https://www.linkedin.com/in/kerryzhu/
- **Guomian Zhuang** `guomian-zhuang` · Head of MemOS R&D, Memory Tensor
- **Nan Zou** `nan-zou` · CANN Architect

## RustChinaConf 2026 (co-located; Oct 15 workshops, Oct 16–17 afternoons; all CST)

### Thu Oct 15 · RustChinaConf Omarchy Shenzhen Meetup · ONES Venue
- 10:00–10:10 **Opening**. Why the terminal returns in the agent era, and the day's flow
- 10:10–10:35 **Omarchy Live Showcase**
- 10:50–12:30 **Why I dare to use Omarchy as my daily driver: recoverable, controllable, naturally evolving** — Nero (Qianji team)
- 10:50–12:30 **Omarchy China: official mirrors and localized services** — Alex Zhang
- 10:50–12:30 **Omarchy × RISC-V**
- 10:50–12:30 **Open call slot**

### Thu Oct 15 · RustChinaConf Afternoon Rust AI Coding Workshop · ONES Venue
- 14:00–16:00 **W1 · Hands-on AI Coding with Rust: From Manual Coding to AI Coding**. A computer-use-agent case: spec-driven work + four guardrails against failures + Libra trajectory replay
- 16:20–18:20 **W2 · Hands-on Embedded Rust: Let AI Modify the Board in Your Hand**. A real vibekeys-max board: hello world → networked recording → AI firmware change flashed back over OTA …
- 18:20–18:30 **Wrap-up & group photo**

### Thu Oct 15 · RustChinaConf Afternoon Solana Session · Aden Hotel Shenzhen Nanshan
- 13:30–14:30 **Solana for Rustaceans**
- 14:30–15:30 **What Is Happening in Blockchain: New Opportunities for Rust Developers**
- 15:50–16:50 **Solana Mini-Class: Build Your First Blockchain App Together**
- 16:50–17:50 **Career Fair**

### Fri Oct 16 · RustChinaConf Morning Plenary · Aden Hotel Shenzhen Nanshan
- 09:30–10:15 **GOSIM Keynote**. Attendee guidance
- 10:15–10:25 **RustChinaConf Opening**
- 10:25–10:27 **Diamond Sponsor Remarks**
- 10:27–10:57 **Symposium: Embracing Every Ecosystem** — Jack Huey (Types Team Lead, Rust Project · Project Director, Rust Foundation Board). Frontier models can generate substantial amounts of code, but new language features, private libraries …
- 11:05–11:35 **Rust × AI: Architecture and Engineering of vivo BlueOS** — He Cheng (System R&D Director, vivo). Since 2019, vivo has built BlueOS in Rust. This talk presents the architecture and engineering lessons behind BlueOS's full-stack Rust …
- 11:35–12:00 **Moonshot AI / Kimi: Analyzing AI-Generated Rust Projects** — FeiHu Tang (Developer Relations Lead & R&D Engineer, Moonshot AI). Drawing on public benchmarks such as Multi-SWE-bench and Rust-SWE-bench and on real vibe-coded repositories …
- 17:05–17:05 **Afternoon sessions end · Track wrap-up**

### Fri Oct 16 · RustChinaConf Qihang 1 · Aden Hotel Shenzhen Nanshan
- 14:00–14:30 **Bringing Rust into vLLM: Designing and Evolving the Inference Frontend** — Bugen Zhao (Member of Technical Staff, Inferact · vLLM Committer · Rust Frontend Code Owner). Inference frontends now carry growing CPU work and protocol semantics: chat templates, tokenization and incremental decoding …
- 14:40–15:10 **When Users Are No Longer Only Human: Building an Agent-Oriented JSON Database in Rust** — Fucong Luo (GreptimeDB Engineer, Greptime). When AI agents consume observability data, schemas must become discoverable …
- 15:15–15:45 **Curvine: A Rust AI & Cloud-Native File System** — David Fu (Big Data Architecture Tech Lead, OPPO · Founder of Curvine). Object storage is cheap and scalable, but its high latency, weak metadata …
- 16:00–16:30 **Cache Locality and Load Balancing: Rust Engineering in SGLang Router** — Tony Lu (AI Inference Expert, Alibaba · Linux SMC Subsystem Maintainer · SGLang Contributor). Once LLM serving scales to many instances, the router must manage dynamic workers, track load and KV-cache placement …
- 16:35–17:05 **BrewFS: Building a Distributed File System for AI Agents in Rust** — Xiaoyang Han (PhD Student, School of Computer Science, Nanjing University). Agents constantly write code and intermediate artifacts: shared directories conflict, copying workspaces is costly …

### Fri Oct 16 · RustChinaConf Qihang 2 · Aden Hotel Shenzhen Nanshan
- 14:00–14:30 **RustBot: A Workflow for Producing Production-Grade Rust Code** — Mingyu Chen (Senior Engineer, Huawei). AI makes writing code cheap, but production Rust must be trustworthy, traceable, and maintainable.
- 14:40–15:10 **AI Agents for Generating and Reviewing Unsafe Rust Safety Documentation** — Yilin Chen (Graduate Student, Fudan University · Rust & Rust-for-Linux Contributor). Whether agents can write safety documentation for unsafe APIs is still debated.
- 15:15–15:45 **An Introduction to RustScript** — Wangchong Zhou (fffonion) (AI Gateway Tech Lead, Kong). RustScript is a scripting language that looks like Rust and embeds into Rust applications.
- 16:00–16:30 **Speeding Up with AI Without Sacrificing Quality: Multi-Layer Automated Testing at RustFS** — Jinghe Ma (Core Contributor, RustFS · Co-Host of Open Source Face-to-Face). After adopting GPT, Claude Code, and GLM, the RustFS team sped up dramatically but found that more PRs meant more regressions …
- 16:35–16:45 **Why Compiler Certification Matters** — Allen Wyma (Director, Plangora Limited · Host, Rustacean Station Podcast). Open source and safety are two parallel ecosystems, but they are slowly coming together.
- 16:45–16:55 **Vue Without JavaScript: A New Rust Approach to Embedded UI** — HalfSweet (Co-Founder, Pocket Nexus · Full-Stack Embedded Software Engineer). Can you write embedded UIs in Vue without running a JavaScript engine on the MCU? Drawing on PocketJS …
- 16:55–17:05 **BitRouter: Workflow-Driven Model Routing for Agents** — HongYi Yang (Archer) (Co-Founder & CTO, BitRouterAI). Agents often send planning, tool calls, and debugging all to the same expensive model.

### Fri Oct 16 · RustChinaConf Qihang 3 · Aden Hotel Shenzhen Nanshan
- 14:00–14:30 **Building Rust Security Gateways with Pingora at Alibaba Cloud** — Zuxi Wang (Jinjiu) (Technical Expert, Alibaba Cloud · Rust Gateway Lead for Security Products). For over a decade, the forwarding engine behind Alibaba Cloud's WAF and Anti-DDoS ran on Nginx/Tengine + Lua …
- 14:40–15:10 **AI-Assisted Evolution of a Production QUIC Gateway** — Yuyang Lu (Software Engineer, Cloud-Native Platform Team, Xiaohongshu). ROFF, Xiaohongshu's in-house QUIC gateway, carries the main site's core traffic.
- 15:15–15:45 **Building a Cross-Platform Audio/Video Client with Rust + Iced** — Jinti Shen (Tech Lead, Miuda · RustPBX Developer). Instead of heavyweight stacks such as Tauri or GPUI, this talk builds a frequently used cross-platform audio/video client with Iced and …
- 16:00–16:30 **Inside Rustup: From Toolchain Management to Ecosystem Infrastructure** — Li Gen (rami3l) (Maintainer in Residence, Rust Foundation · Rustup Team Lead). Rustup is the main entry point for installing, managing, and using Rust toolchains.
- 16:35–17:05 **Building an AI-Native Version-Control Engine in Rust** — Yonghe Wang (Co-Founder, GitMono). AI coding agents read issues, edit code, and open PRs, yet workflows usually keep only the final commit and CI result, while prompts …

### Sat Oct 17 · RustChinaConf Morning Plenary · Aden Hotel Shenzhen Nanshan
- 09:30–10:15 **GOSIM keynote**
- 10:15–10:20 **Day 2 opening + Diamond sponsor address**
- 10:20–10:50 **The Next Decade of Rust** — Rebecca Rumbul (Executive Director & CEO, Rust Foundation). More than a decade after Rust 1.0, Rust Foundation Executive Director and CEO Rebecca Rumbul looks back on Rust's first decade and …
- 10:50–11:20 **From Low-Latency Systems to AI Agents: Nonconvex Tech's Open-Source Rust Practice** — Guoli Lv (Author of ftlog, Nonconvex Tech). Nonconvex's core trading system is Rust end to end with microsecond latency targets, where synchronous logging slows the critical path.
- 11:20–11:40 **Rust as an Ecosystem-Builder** — Hunter Bown (CEO, Shannon Labs · Author of CodeWhale). Rust's reputation is backwards. What made it 'hard' — a compiler that refuses ambiguity, errors that teach …
- 11:40–12:10 **Visualising Large Codebases and AI Agent Activity with Makepad** — Rik Arends (Co-Founder, Makepad · Co-Founder, Cloud9 IDE). In this talk I will show how I use Makepad to visualise large codebases, a demo that got over 2 million views on X.
- 17:45–17:50 **Closing talk**
- 17:50–18:10 **Thanks and departure**

### Sat Oct 17 · RustChinaConf Qihang 1 · Aden Hotel Shenzhen Nanshan
- 14:00–14:30 **cuda-oxide: CUDA Kernels in Pure Rust** — Nihal Pasham (Senior Software Engineer, NVIDIA · Author & Maintainer of cuda-oxide). Writing CUDA kernels in Rust often means separate crates or extra bindings.
- 14:40–15:10 **Inside Sail: Rebuilding Spark in Rust** — Heran Lin (Co-Founder & CTO, LakeSail). Sail is an Apache-2.0, JVM-free compute engine written in Rust. It preserves compatibility with PySpark SQL/DataFrame workloads through …
- 15:15–15:45 **A New Framework for Personal Data-Driven Agents** — Peng Zhang (Beihai) (Founder, Genmeta Tech · DHttp Evangelist). Alice's and Bob's AI assistants run on Mac Minis at home. How can they connect securely and affordably? DHttp pairs each private endpoint …
- 16:00–16:30 **Rust and the Lights-Out Software Factory** — Alex Zhang (Chief Technical Consultant, Singularity Intelligence Research Institute · Chief Evangelist, Rust Chinese Community · Co-Founder, RustChinaConf · Core Developer, Octos Agent OS). AI coding is collapsing the cost of producing code, shifting the bottleneck from generating more code to constraining and verifying it.
- 16:35–17:15 **Rust and the Software Factory**. As agents learn to plan, code, test, and fix continuously, practitioners from open-source infrastructure, databases, multimedia …

### Sat Oct 17 · RustChinaConf Qihang 2 · Aden Hotel Shenzhen Nanshan
- 14:00–14:30 **Trust Me, It's Faster: Rounding a Float** — Adrien Cacciaguerra (Co-Founder & CTO, CodSpeed). I went looking for something to optimize in `image`, one of Rust's most-downloaded crates, and landed on `fast_blur`.
- 14:40–15:10 **An RSI Agent That Rewrites Its Own Rust Code** — Michael Yuan (WasmEdge Maintainer). In a recursively self-improving agent, newly generated code becomes part of the agent itself and is then executed to produce the next …
- 15:15–15:45 **Formal Web** — Gregory Terzian (Servo Contributor · Formal Web Developer). This talk introduces the Rust-based Formal Web project and explores how formal methods can be brought into the Web platform to create …
- 16:00–16:30 **The Interactive Art of Rust: Rebuilding Multimedia Workflows with the Rust Stack** — Shenghao Ding (Delton) (CEO, Yet Another AI Ltd). Multimedia toolchains for games and music depend heavily on C/C++ ABIs, platform graphics and audio APIs …
- 16:35–17:05 **Machine-Checking Rust in the AI Era: Building an Auditable Chain of Evidence** — Qining Lin (Senior Engineer, YaKoo Technology · Zchain Developer & Maintainer). AI lets Rust implementations, tests, and even formal proofs grow fast, but what do "it compiles", "all green" …
- 17:10–17:40 **Letting Agents Drive the Work: Building Holon's Event-Driven Agent Runtime in Rust** — Jolestar (Author of Holon · Open-Source Developer). Real-world engineering work is inherently long-running and event-driven, often waiting on external CI builds, human approvals …

### Sat Oct 17 · RustChinaConf Qihang 3 · Aden Hotel Shenzhen Nanshan
- 14:00–14:30 **Very Local: AI and Rust for an Embedded NPU** — Bart Massey (Associate Professor of Computer Science, Portland State University · Rust Embedded Working Group Member). On the Axon NPU inside Nordic's nRF54LM20B, AI is used to analyze binary drivers and C headers and generate bare-metal Rust wrappers …
- 14:40–15:10 **Build What Production Needs: Creating Rust Infrastructure with AI Agents** — Zili Chen (tison) (Co-Founder, ScopeDB · ASF Board Member · Apache OpenDAL Maintainer). Taking the cloud database ScopeDB to production needs a lot of foundational Rust …
- 15:15–15:45 **Scaling Rust in the Enterprise: What Happens as Rust Projects Grow** — Songsong Fan (Director of Solutions, APAC, Incredibuild). A small Rust project usually compiles without trouble. As the codebase grows, with more crates, more complex dependency graphs …
- 16:00–16:30 **Robrix A2App: A Matrix Collaboration Space for Humans and Agents** — Kevin Boos (Chief Architect, Futurewei · Creator of Theseus OS · Technical Lead, Robius Project); Gregory Terzian (Servo Contributor). Built on the Rust-native Matrix client Robrix, this talk explores communication, tasks …
- 16:35–17:05 **mq9: Mailbox-Style Asynchronous Messaging Infrastructure for AI Agents** — Lobo Xu (Author of RobustMQ · Former Kafka/RabbitMQ Tech Lead, Tencent Cloud). In multi-agent systems, agents sleep for hours or go offline, and human approvals can step in mid-workflow.
- 17:10–17:40 **Arkret: Building Trusted Human–AI Collaboration Infrastructure in Rust** — Xuecheng Yang (Author & Maintainer of Salvo and Palpo · Arkret Developer). As AI becomes a real collaborator, what can it see, what can it do, which actions need confirmation …

### Sat Oct 17 · RustChinaConf Parallel meeting · closed workshop · Aden Hotel Shenzhen Nanshan
- 09:30–17:00 **🔒 OpenAtom Xuanwu Open Source Community | Rust teacher training and teaching seminar · closed all day (Hailiao Hall, 09:30–17:00)**

## Spotlight Shenzhen 2026 — 18 selected AI-native product projects (booths both days + a main-stage showcase slot)
- 01 **Fugleramme** — An e-ink picture frame that identifies birdsong locally and displays natural-history illustrations. https://github.com/arnegiacomo/fugleramme
- 02 **Tiny Engineer** — A desktop robot that turns a coding agent’s status into movements, expressions, lights, and sounds. https://github.com/jamro/tiny-engineer
- 03 **XLeRobot** — A low-cost, open-source mobile robot with two arms and a voice-and-vision agent for navigation and manipulation. https://xlerobot.readthedocs.io/en/latest/
- 04 **很 Local 实时翻译** — Local live translation on Apple Silicon, turning conference speech into bilingual subtitles for GOSIM. https://henlocal.com/
- 05 **VibeKeys** — A physical remote for coding agents, with buttons, a dial, voice input, and a status display. https://vibekeys.dev
- 06 **事务官座机** — A desk-phone interface connecting a computer, phone, and handset to coordinate AI work and follow progress. https://www.aibooo.cn/
- 07 **第三红岸 Redbank III** — An open-source telescope network whose AI agent receives astronomy alerts and coordinates distributed observing nodes. https://redbank-iii.org/sim/
- 08 **橘一下 reset** — A transition agent using voice, vision, and physical interaction to guide attention from screens back to the real world. https://www.resetcat.xyz/#real-demo
- 09 **虾盘 Xiapan USB** — A portable AI computer-maintenance assistant on a USB drive, carrying tools, conversations, reports, and settings. https://usb.u-claw.org.cn/
- 10 **PhyAgentOS** — An open-source runtime for physical agents, combining robot integration, reusable skills, execution, and reflection. https://phy-agent-os.x-era.com/
- 11 **Meiso Glass** — A wireless split AR platform exploring object recognition, spatial panels, voice interaction, and everyday AI assistance. https://drive.google.com/file/d/1McSmbIymFyLMlMP6jSEKJtLBvM3ihgrt/view
- 12 **Ingora · Qrio** — A voice-first AI language companion for children aged 6–12, adapting practice to their level, interests, and progress. https://www.alipan.com/s/NUPgSx13cmG
- 13 **PoopSense 便知** — A toilet-side sensor and AI agent that reduces manual logging and helps families review everyday patterns over time. https://poopsense.org/
- 14 **Mira Light** — A lamp-shaped desktop companion exploring natural interaction through multimodal sensing and expressive movement. https://mira-light.notion.site/lunchbox
- 15 **Octos Learn** — An AI math whiteboard combining spoken questions, handwriting, and camera input with interactive visual explanations. https://learn.pitun.cc
- 16 **Agentero** — An agent-friendly research-paper reader bringing AI agents into the full literature-reading workflow. https://agentero.app
- 17 **Petoi Quaddle** — A programmable mini robot dog for STEM and Physical AI, using just four servos for agile movement and hands-on customization. https://www.kickstarter.com/projects/petoi/quaddle-open-source-desktop-robot-kit/
- 18 **AI视觉创意大赛“瓦卡奖”** — An AI visual creativity competition and exchange platform, connecting creators, artists, technical experts, and industry through contests, forums, and workshops. https://www.lg.gov.cn/gab/zwdt/content/post_12890791.html
<!-- catalog:end -->
