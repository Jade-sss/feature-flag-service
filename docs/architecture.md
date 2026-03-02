# Architecture Flow Diagram

This document describes the request lifecycle and data flow of the Feature Flag Service.

## Request Lifecycle

```mermaid
flowchart TB
    Client([Client / SDK])

    subgraph Edge["Edge Layer"]
        CORS[CORS Middleware]
        TH[Trusted Host Middleware]
    end

    subgraph Observability["Observability Layer"]
        PROM[Prometheus Middleware<br/>Metrics Collection]
        RL[Rate Limiter<br/>Sliding Window per IP]
        SEC[Security Headers<br/>Middleware]
        LOG[Request Logging<br/>X-Request-ID]
    end

    subgraph Auth["Authentication"]
        APIH{X-API-Key Header}
        MASTER[Master Key Check]
        DBKEY[DB Key Lookup<br/>SHA-256 Hash]
        ROLE{Role Check}
    end

    subgraph App["Application Layer"]
        ROUTER[FastAPI Router]
        EVAL[Evaluation Engine]
        CRUD[Flag CRUD]
        KEYS[API Key Mgmt]
    end

    subgraph Data["Data Layer"]
        CACHE[(Redis Cache<br/>Flag + Eval TTL)]
        DB[(PostgreSQL<br/>Feature Flags<br/>Overrides<br/>API Keys)]
    end

    subgraph Ops["Observability Endpoints"]
        HEALTH[/health]
        METRICS[/metrics]
    end

    Client -->|HTTP Request| CORS
    CORS --> TH
    TH --> PROM
    PROM --> RL
    RL -->|429 if exceeded| Client
    RL --> SEC
    SEC --> LOG
    LOG --> ROUTER

    ROUTER --> APIH
    APIH -->|Missing| Client
    APIH --> MASTER
    MASTER -->|Match| ROLE
    MASTER -->|No Match| DBKEY
    DBKEY -->|Invalid| Client
    DBKEY -->|Valid| ROLE
    ROLE -->|Forbidden| Client
    ROLE -->|Authorized| App

    ROUTER --> EVAL
    ROUTER --> CRUD
    ROUTER --> KEYS

    EVAL -->|1. Check Cache| CACHE
    EVAL -->|2. Load Flag| DB
    EVAL -->|3. User Override?| DB
    EVAL -->|4. Cache Result| CACHE

    CRUD --> DB
    CRUD -->|Invalidate| CACHE
    KEYS --> DB

    ROUTER --> HEALTH
    ROUTER --> METRICS
    HEALTH -->|Ping| DB
    HEALTH -->|Ping| CACHE
    METRICS -->|Scrape| PROM

    style Edge fill:#e3f2fd,stroke:#1565c0
    style Observability fill:#fff3e0,stroke:#e65100
    style Auth fill:#fce4ec,stroke:#c62828
    style App fill:#e8f5e9,stroke:#2e7d32
    style Data fill:#f3e5f5,stroke:#6a1b9a
    style Ops fill:#eceff1,stroke:#455a64
```

## Evaluation Flow (Detail)

```mermaid
flowchart TD
    START([GET /flags/evaluate<br/>?key=...&user_id=...])
    C1{Eval cache<br/>hit?}
    C2{Flag exists<br/>in DB?}
    C3{Per-user<br/>override?}
    C4{Flag globally<br/>enabled?}
    C5{Rollout %<br/>configured?}
    C6{User in<br/>rollout %?}
    RET_T([enabled: true])
    RET_F([enabled: false])
    CACHE_W[Cache result<br/>TTL 60s]

    START --> C1
    C1 -->|Hit| RET_T
    C1 -->|Hit false| RET_F
    C1 -->|Miss| C2
    C2 -->|No| RET_F
    C2 -->|Yes| C3
    C3 -->|Override=true| CACHE_W --> RET_T
    C3 -->|Override=false| CACHE_W
    C3 -->|No override| C4
    C4 -->|Yes| CACHE_W
    C4 -->|No| C5
    C5 -->|No| RET_F
    C5 -->|Yes| C6
    C6 -->|In %| CACHE_W
    C6 -->|Out| RET_F

    style START fill:#e3f2fd
    style RET_T fill:#c8e6c9
    style RET_F fill:#ffcdd2
```

## Data Model

```mermaid
erDiagram
    FEATURE_FLAGS {
        int id PK
        string key UK "max 200 chars, ^[a-zA-Z0-9._-]+$"
        text description
        bool is_enabled "default false"
        int rollout_percentage "0-100, nullable"
        json conditions "targeting rules"
        datetime created_at
        datetime updated_at
    }

    FLAG_OVERRIDES {
        int id PK
        int flag_id FK
        string user_id "max 200 chars"
        bool enabled
        datetime created_at
    }

    API_KEYS {
        int id PK
        string key_hash UK "SHA-256, 64 chars"
        string key_prefix "first 8 chars"
        string name "max 200 chars"
        enum role "admin | readonly"
        bool is_active "soft delete"
        datetime created_at
    }

    FEATURE_FLAGS ||--o{ FLAG_OVERRIDES : "has overrides"
```
