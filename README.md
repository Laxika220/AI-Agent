# ⚒️ AgentForge

**A multi-agent AI platform with tool-calling, RAG and agent orchestration.**
Build custom AI agents, give them tools and a knowledge base, chat with them over a streaming UI, and chain them together into multi-step pipelines.

![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React_18-20232A?logo=react&logoColor=61DAFB)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?logo=langchain&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-47A248?logo=mongodb&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white)

> 📸 _Screenshots: add `docs/screenshots/{dashboard,chat,chains}.png` here._

---

## ✨ Features

| | |
|---|---|
| 🤖 **Custom agents** | System prompt, model, temperature, tools and an optional knowledge base per agent |
| 🛠️ **Tool-calling** | Web search (DuckDuckGo), safe calculator (numexpr), sandboxed Python execution, JSON API calls |
| 📚 **RAG pipeline** | PDF / DOCX / TXT / MD → recursive chunking → local embeddings (`all-MiniLM-L6-v2`) → ChromaDB → MMR retrieval |
| ⚡ **Streaming chat** | Server-Sent Events stream tokens, tool calls (with inputs/outputs) and retrieved passages live |
| 🔗 **Multi-agent chains** | DAG of agents; independent steps run **in parallel**; full execution trace with per-step timing |
| 🔐 **Auth** | JWT access (15 min) + single-use rotating refresh tokens (7 days), bcrypt password hashing |
| 🚦 **Redis** | Conversation context cache (last 20 messages), per-user rate limiting (10 req/min), embedding cache |
| 🔌 **Any OpenAI-compatible LLM** | OpenAI, Groq, Together, OpenRouter, local Ollama — configured with two env vars |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                    React Frontend                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │Agent     │  │Document  │  │Chat Interface     │  │
│  │Builder   │  │Uploader  │  │(Streaming SSE)    │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
└────────────────────────┬────────────────────────────┘
                         │ REST API + SSE
┌────────────────────────▼────────────────────────────┐
│                   FastAPI Backend                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │Agent     │  │RAG       │  │Tool Execution     │  │
│  │Orchestr. │  │Pipeline  │  │Engine             │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │Auth/JWT  │  │SSE       │  │Agent Chaining     │  │
│  │          │  │Streaming │  │(Multi-Agent)      │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
└──┬──────────┬──────────┬──────────┬─────────────────┘
   │          │          │          │
┌──▼──┐  ┌───▼──┐  ┌───▼───┐  ┌──▼───┐
│Mongo│  │Redis │  │Chroma │  │Tools │
│DB   │  │Cache │  │VectorDB│ │(APIs)│
└─────┘  └──────┘  └───────┘  └──────┘
```

### How a chat request flows

1. `POST /chat/{agent_id}` → rate-limit check (Redis) → load the last 20 messages (Redis, falling back to MongoDB).
2. The agent's tools are resolved from the registry; if the agent has a knowledge base, a `retrieve_context` tool bound to its ChromaDB collection is added.
3. LangChain's `create_tool_calling_agent` + `AgentExecutor` runs the loop. `astream_events` is mapped to SSE events: `token`, `tool_start`, `tool_end`, `retrieval`, `done`.
4. The final answer and tool calls are persisted in MongoDB and appended to the Redis context cache.

### How a chain runs

Steps form a dependency graph. The runner groups steps into **topological levels** (Kahn's algorithm) and runs each level concurrently with `asyncio.gather`. A step with one upstream step receives that output as its message; a step with several receives the original request plus every upstream output. If a step fails, the steps after it are marked `skipped` and the run reports `partial`.

---

## 🧰 Tech stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, Pydantic v2, pydantic-settings, structlog |
| AI | LangChain (tool-calling agent), langchain-openai, sentence-transformers |
| Vector store | ChromaDB (cosine HNSW, MMR re-ranking) |
| Database | MongoDB 7 (PyMongo async) |
| Cache / rate limit | Redis 7 |
| Frontend | React 18, Vite, Tailwind CSS, React Router, axios, react-markdown |
| Auth | PyJWT, bcrypt |
| Infra | Docker, Docker Compose, nginx |

---

## 🚀 Quick start (Docker Compose)

```bash
git clone https://github.com/Laxika220/AI-Agent.git
cd AI-Agent
cp backend/.env.example backend/.env      # then set OPENAI_API_KEY (and optionally MODEL_NAME / OPENAI_BASE_URL)
docker compose up --build
```

| Service | URL |
|---|---|
| Web app | http://localhost:3000 |
| API + Swagger docs | http://localhost:8000/docs |
| ChromaDB | http://localhost:8001 |

> The first build downloads CPU-only PyTorch and bakes in the embedding model, so it takes a few minutes and needs roughly 5 GB of free disk space. After that it starts in seconds.
>
> Port already in use (for example a local MongoDB)? Override the host ports: `MONGO_HOST_PORT=27018 REDIS_HOST_PORT=6380 CHROMA_HOST_PORT=8002 docker compose up --build`.

### Using a different LLM provider

Any OpenAI-compatible API works:

```bash
# Groq
OPENAI_BASE_URL=https://api.groq.com/openai/v1
OPENAI_API_KEY=gsk_...
MODEL_NAME=llama-3.3-70b-versatile

# Local Ollama (from inside Docker)
OPENAI_BASE_URL=http://host.docker.internal:11434/v1
OPENAI_API_KEY=ollama
MODEL_NAME=llama3.1
```

> Tool-calling requires a model that supports function calling.

---

## 🧑‍💻 Local development

**Infrastructure only**

```bash
docker compose up -d mongodb redis chromadb
```

**Backend** (Python 3.12)

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env    # set OPENAI_API_KEY
uvicorn app.main:app --reload
pytest                  # unit tests
```

**Frontend** (Node 20)

```bash
cd frontend
npm install
npm run dev             # http://localhost:5173, proxies /api → localhost:8000
```

---

## 📡 API reference

Interactive docs live at `/docs` (Swagger) and `/redoc`. All routes except `/auth/*` and `/health` need `Authorization: Bearer <access_token>`.

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/auth/register` | Create account → user + token pair |
| `POST` | `/auth/login` | Log in → user + token pair |
| `POST` | `/auth/refresh` | Exchange a refresh token (single-use) for a new pair |
| `GET` | `/auth/me` | Current user |
| `GET` `POST` | `/agents` | List / create agents |
| `GET` `PUT` `DELETE` | `/agents/{id}` | Read / update / delete an agent |
| `GET` `POST` | `/knowledge-bases` | List / create knowledge bases |
| `DELETE` | `/knowledge-bases/{id}` | Delete a knowledge base, its documents and vectors |
| `POST` | `/documents/upload` | Multipart upload (`file`, `knowledge_base_id`) → processed in the background |
| `GET` | `/documents?knowledge_base_id=` | List documents with processing status |
| `DELETE` | `/documents/{id}` | Delete a document and its chunks |
| `POST` | `/chat/{agent_id}` | **SSE stream**: `conversation`, `token`, `tool_start`, `tool_end`, `retrieval`, `done`, `error` |
| `GET` | `/chat/conversations` | List conversations (`?agent_id=`) |
| `GET` `DELETE` | `/chat/conversations/{id}` | Conversation with messages / delete |
| `GET` `POST` | `/chains` | List / create chains |
| `GET` `PUT` `DELETE` | `/chains/{id}` | Read / replace / delete a chain |
| `POST` | `/chains/{id}/run` | Execute a chain → full trace with timing |
| `GET` | `/chains/{id}/runs` | Recent runs |
| `GET` | `/tools` | Available tools and their parameter schemas |
| `GET` | `/models` | Default and selectable LLM models |
| `GET` | `/health` | MongoDB / Redis / ChromaDB status |

<details>
<summary><b>Example: streaming chat with curl</b></summary>

```bash
curl -N -X POST http://localhost:8000/chat/$AGENT_ID \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"message": "What is 17% of 2340? Then search who invented the transistor."}'
```

```
event: conversation
data: {"conversation_id": "9f1c...", "user_message_id": "a2b4..."}

event: tool_start
data: {"type": "tool_start", "run_id": "...", "tool_name": "calculator", "input": {"expression": "0.17 * 2340"}}

event: tool_end
data: {"type": "tool_end", "tool_name": "calculator", "output": 397.8, "error": null, "duration_ms": 2.1}

event: token
data: {"type": "token", "content": "17% of 2340 is **397.8**"}
...
event: done
data: {"id": "...", "role": "assistant", "content": "...", "tool_calls": [...]}
```
</details>

<details>
<summary><b>Example: a chain with parallel steps</b></summary>

```json
{
  "name": "Research → Write",
  "steps": [
    {"id": "web",    "agent_id": "<researcher>",   "depends_on": []},
    {"id": "docs",   "agent_id": "<kb-analyst>",   "depends_on": []},
    {"id": "write",  "agent_id": "<writer>",       "depends_on": ["web", "docs"]},
    {"id": "edit",   "agent_id": "<editor>"}
  ]
}
```

`web` and `docs` run in parallel, `write` merges their outputs, and `edit` (`depends_on` omitted = previous step) polishes the result.
</details>

Errors always use the same format:

```json
{"error": {"code": "rate_limited", "message": "Rate limit of 10 requests/minute exceeded", "details": {"retry_after": 42}}}
```

---

## ⚙️ Environment variables

See [`backend/.env.example`](backend/.env.example) for the full annotated list.

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | API key for the LLM provider (**required**) |
| `OPENAI_BASE_URL` | _(OpenAI)_ | Base URL of any OpenAI-compatible API |
| `MODEL_NAME` | `gpt-4o-mini` | Default chat model |
| `AVAILABLE_MODELS` | `["gpt-4o-mini", …]` | Models offered in the agent builder |
| `MONGO_URI` / `MONGO_DB` | `mongodb://localhost:27017` / `agentforge` | MongoDB connection |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `CHROMA_HOST` / `CHROMA_PORT` | `localhost` / `8001` | ChromaDB server (leave host empty for embedded on-disk mode) |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Local embedding model |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `1000` / `200` | Text splitter settings |
| `RETRIEVAL_TOP_K` / `RETRIEVAL_FETCH_K` / `MMR_LAMBDA` | `5` / `20` / `0.5` | Retrieval and MMR diversity |
| `JWT_SECRET_KEY` | — | **Change in production** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | `15` / `7` | Token lifetimes |
| `RATE_LIMIT_PER_MINUTE` | `10` | Chat / chain requests per user per minute |
| `CONVERSATION_CACHE_SIZE` | `20` | Messages of context kept per conversation |
| `MAX_UPLOAD_MB` | `20` | Upload size limit |
| `CODE_EXEC_TIMEOUT_SECONDS` | `10` | Sandbox wall-clock / CPU limit |
| `ALLOW_PRIVATE_NETWORK_API_CALLS` | `false` | Let `json_api_call` reach private IPs (dev only) |
| `LOG_LEVEL` / `LOG_JSON` | `INFO` / `false` | structlog output |

---

## 📁 Project structure

```
.
├── backend/
│   ├── app/
│   │   ├── main.py               # App factory, lifespan, middleware, /health
│   │   ├── config.py             # pydantic-settings
│   │   ├── core/                 # logging, errors, database, middleware, dependencies
│   │   ├── models/               # Pydantic v2 schemas (user, agent, document, conversation, chain)
│   │   ├── routes/               # auth, agents, knowledge_bases, documents, chat, chains, tools
│   │   ├── services/
│   │   │   ├── rag_pipeline.py   # extract → chunk → embed → ChromaDB → MMR retrieve
│   │   │   ├── agent_executor.py # LangChain tool-calling agent + event streaming
│   │   │   ├── tool_registry.py  # web_search, calculator, code_executor, json_api_call
│   │   │   ├── chain_runner.py   # DAG orchestration with parallel levels
│   │   │   └── redis_cache.py    # context cache, rate limiting, embedding cache
│   │   └── utils/                # auth, chunking, embeddings, extraction, graph
│   ├── tests/                    # pytest unit tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/client.js         # axios + JWT refresh interceptor
│   │   ├── hooks/                # useAuth, useSSE, useAgents
│   │   ├── components/           # AgentBuilder, ChatInterface, ToolCallDisplay, ChainBuilder, …
│   │   └── pages/                # Dashboard, Agents, Chat, Documents, Chains, Login, Register
│   ├── nginx.conf
│   └── Dockerfile
└── docker-compose.yml
```

---

## 🔒 Security notes

- **Code execution** runs in a separate `python -I` process with CPU, memory, file-size and open-file limits, a throwaway working directory and a minimal environment. This is defence in depth, **not** a hard security boundary. For untrusted multi-tenant use, run it in gVisor, Firecracker or a separate container.
- **`json_api_call`** only allows http(s), resolves DNS and blocks private, loopback, link-local and metadata addresses, and does not follow redirects (basic SSRF protection).
- **Calculator** input is whitelisted (characters and function names) before it reaches `numexpr`.
- Refresh tokens are single-use: replaying a refresh token is rejected.

---

## 🗺️ Future improvements

- [ ] Stream chain execution step by step over SSE
- [ ] Hybrid retrieval (BM25 + vectors) and a cross-encoder re-ranker
- [ ] Per-agent memory summarisation for long conversations
- [ ] Usage metering (tokens/cost per agent) and tiered rate limits
- [ ] Background job queue (Celery/ARQ) for large document ingestion
- [ ] OAuth sign-in and team workspaces with shared agents
- [ ] Container-isolated code sandbox
- [ ] Evaluation harness for RAG quality (faithfulness, answer relevance)

---

## 📄 License

MIT
