# Flow Diagrams

This document contains comprehensive flow diagrams for the dYdX Trading Bot system using Mermaid syntax. These diagrams illustrate the key processes and decision flows within the trading bot.

## 🚀 Main Execution Flow

```mermaid
flowchart TD
    A[Bot Startup] --> B[Initialize Logging]
    B --> C[Load Configuration]
    C --> D{Configuration Valid?}
    D -->|No| E[Exit with Error]
    D -->|Yes| F[Send Startup Message]
    F --> G[Connect to dYdX]
    G --> H{Connection Successful?}
    H -->|No| I[Exit with Error]
    H -->|Yes| J{Abort All Positions?}
    J -->|Yes| K[Close All Positions]
    K --> L{Find Cointegrated Pairs?}
    J -->|No| L
    L -->|Yes| M[Fetch Market Prices]
    M --> N[Calculate Cointegration]
    N --> O[Store Results to CSV]
    O --> P[Main Trading Loop]
    L -->|No| P
    P --> Q{Manage Exits?}
    Q -->|Yes| R[Process Exit Positions]
    R --> S{Place Trades?}
    Q -->|No| S
    S -->|Yes| T[Find Entry Opportunities]
    T --> U[Execute New Trades]
    U --> V[Sleep Interval]
    S -->|No| V
    V --> P
    
    %% Error Handling
    E --> W[Send Error Message]
    I --> W
    W --> X[Exit Program]
    
    style A fill:#e1f5fe
    style P fill:#f3e5f5
    style X fill:#ffebee
```

## 📊 Cointegration Analysis Flow

```mermaid
flowchart TD
    A[Start Cointegration Analysis] --> B[Load Market Prices DataFrame]
    B --> C[Get Active Markets List]
    C --> D[Initialize Results Container]
    D --> E{More Base Markets?}
    E -->|No| Z[Save Results to CSV]
    E -->|Yes| F[Select Base Market]
    F --> G[Calculate Return Volatility]
    G --> H{Volatility > Threshold?}
    H -->|No| E
    H -->|Yes| I{More Quote Markets?}
    I -->|No| E
    I -->|Yes| J[Select Quote Market]
    J --> K[Calculate Quote Volatility]
    K --> L{Quote Volatility > Threshold?}
    L -->|No| I
    L -->|Yes| M[Perform Cointegration Test]
    M --> N{Test Successful?}
    N -->|No| O[Log Skip Reason]
    O --> I
    N -->|Yes| P[Calculate Hedge Ratio]
    P --> Q[Calculate Half-Life]
    Q --> R{P-Value < 0.05?}
    R -->|No| I
    R -->|Yes| S{Half-Life ≤ 24h?}
    S -->|No| I
    S -->|Yes| T[Add to Results]
    T --> I
    Z --> AA[Return Success]
    
    %% Error handling
    M --> M1{Exception?}
    M1 -->|Yes| M2[Log Error]
    M2 --> I
    M1 -->|No| P
    
    style A fill:#e8f5e8
    style Z fill:#e1f5fe
    style AA fill:#f3e5f5
```

## 📈 Entry Position Flow

```mermaid
flowchart TD
    A[Start Entry Analysis] --> B[Load Cointegrated Pairs CSV]
    B --> C[Get Market Information]
    C --> D[Load Existing Bot Agents]
    D --> E{More Pairs to Check?}
    E -->|No| Z[Save Bot Agents]
    E -->|Yes| F[Select Pair]
    F --> G[Check if Already Trading]
    G --> H{Already Trading Pair?}
    H -->|Yes| E
    H -->|No| I[Get Recent Candles]
    I --> J[Calculate Current Spread]
    J --> K[Calculate Z-Score]
    K --> L{|Z-Score| ≥ 1.5?}
    L -->|No| E
    L -->|Yes| M[Check Account Balance]
    M --> N{Sufficient Collateral?}
    N -->|No| E
    N -->|Yes| O[Calculate Position Sizes]
    O --> P[Determine Trade Sides]
    P --> Q[Create BotAgent]
    Q --> R[Execute Paired Trade]
    R --> S{Trade Successful?}
    S -->|No| T[Log Failed Trade]
    T --> E
    S -->|Yes| U[Add to Bot Agents]
    U --> V[Update State File]
    V --> E
    Z --> W[Log Completion]
    
    %% Sub-process for Z-Score calculation
    K --> K1[Calculate Rolling Mean]
    K1 --> K2[Calculate Rolling Std]
    K2 --> K3[Compute Z-Score]
    K3 --> L
    
    style A fill:#e8f5e8
    style R fill:#fff3e0
    style Z fill:#f3e5f5
```

## 📉 Exit Position Flow

```mermaid
flowchart TD
    A[Start Exit Analysis] --> B[Load Bot Agents JSON]
    B --> C{Any Open Positions?}
    C -->|No| D[Return Complete]
    C -->|Yes| E[Get Exchange Positions]
    E --> F{More Bot Agents?}
    F -->|No| Y[Save Updated Agents]
    F -->|Yes| G[Select Bot Agent]
    G --> H[Get Recent Prices]
    H --> I[Calculate Current Spread]
    I --> J[Calculate Z-Score]
    J --> K{Close at Z-Cross?}
    K -->|Yes| L{Z-Score Crossed Zero?}
    K -->|No| M{Force Close Conditions?}
    L -->|Yes| N[Execute Close Orders]
    L -->|No| F
    M -->|Yes| N
    M -->|No| O[Validate Position Exists]
    O --> P{Position on Exchange?}
    P -->|Yes| F
    P -->|No| Q[Mark for Removal]
    Q --> F
    N --> R{Close Successful?}
    R -->|Yes| S[Remove from Bot Agents]
    R -->|No| T[Mark as Error]
    S --> F
    T --> F
    Y --> Z[Return Complete]
    
    %% Force close conditions
    M --> M1{Position Mismatch?}
    M1 --> M2{Emergency Mode?}
    M2 --> M
    
    style A fill:#e8f5e8
    style N fill:#ffebee
    style Z fill:#f3e5f5
```

## 🤖 BotAgent State Machine

```mermaid
stateDiagram-v2
    [*] --> INITIALIZING
    INITIALIZING --> PLACING_FIRST_ORDER : create_bot_agent()
    
    PLACING_FIRST_ORDER --> CHECKING_FIRST_ORDER : first_order_placed
    PLACING_FIRST_ORDER --> FAILED : first_order_failed
    
    CHECKING_FIRST_ORDER --> PLACING_SECOND_ORDER : first_order_live
    CHECKING_FIRST_ORDER --> FAILED : first_order_not_live
    
    PLACING_SECOND_ORDER --> CHECKING_SECOND_ORDER : second_order_placed
    PLACING_SECOND_ORDER --> ERROR : second_order_failed
    
    CHECKING_SECOND_ORDER --> LIVE : second_order_live
    CHECKING_SECOND_ORDER --> ERROR : second_order_not_live
    
    LIVE --> CLOSING : exit_signal_triggered
    LIVE --> ERROR : position_mismatch
    
    CLOSING --> CLOSED : close_orders_successful
    CLOSING --> ERROR : close_orders_failed
    
    ERROR --> CLOSING : manual_intervention
    ERROR --> FAILED : unrecoverable_error
    
    FAILED --> [*]
    CLOSED --> [*]
    
    note right of FAILED : Logs error details\nSends alert message
    note right of LIVE : Monitors for exit conditions\nTracks P&L
    note right of ERROR : Attempts failsafe closure\nRequires attention
```

## 🔄 Order Execution Subprocess

```mermaid
sequenceDiagram
    participant BE as Bot Engine
    participant BA as BotAgent
    participant DC as dYdX Client
    participant EX as dYdX Exchange
    
    BE->>BA: create_bot_agent(params)
    BA->>BA: initialize_order_dict()
    BA->>DC: place_market_order(market_1)
    DC->>EX: submit_order
    EX-->>DC: order_response
    DC-->>BA: order_id_1
    
    BA->>BA: sleep(0.5s)
    BA->>DC: check_order_status(order_id_1)
    DC-->>BA: "live"
    
    alt First order successful
        BA->>DC: place_market_order(market_2)
        DC->>EX: submit_order
        EX-->>DC: order_response
        DC-->>BA: order_id_2
        
        BA->>BA: sleep(0.5s)
        BA->>DC: check_order_status(order_id_2)
        DC-->>BA: "live"
        
        alt Both orders successful
            BA->>BA: set_status("LIVE")
            BA-->>BE: return success
        else Second order failed
            BA->>DC: place_market_order(close_first)
            BA->>BA: set_status("ERROR")
            BA-->>BE: return error
        end
    else First order failed
        BA->>BA: set_status("FAILED")
        BA-->>BE: return failure
    end
```

## 💾 State Management Flow

```mermaid
flowchart TD
    A[Bot Startup] --> B[Check bot_agents.json]
    B --> C{File Exists?}
    C -->|No| D[Initialize Empty Array]
    C -->|Yes| E[Load Existing Positions]
    E --> F[Validate Against Exchange]
    F --> G{Positions Match?}
    G -->|No| H[Reconcile Differences]
    G -->|Yes| I[Continue Normal Operation]
    H --> J[Remove Orphaned Positions]
    J --> K[Log Discrepancies]
    K --> I
    D --> I
    
    I --> L[Trading Operations]
    L --> M[Position Changes]
    M --> N[Update bot_agents.json]
    N --> O[Atomic Write Operation]
    O --> P{Write Successful?}
    P -->|Yes| Q[Continue Trading]
    P -->|No| R[Log Error]
    R --> S[Retry Write]
    S --> P
    Q --> L
    
    %% Shutdown process
    Q --> T{Shutdown Signal?}
    T -->|Yes| U[Final State Save]
    T -->|No| L
    U --> V[Clean Exit]
    
    style A fill:#e1f5fe
    style V fill:#e8f5e8
    style R fill:#ffebee
```

## 🔔 Error Handling & Recovery

```mermaid
flowchart TD
    A[Error Detected] --> B{Error Type?}
    
    B -->|API Error| C[Check Connection]
    C --> D{Connection OK?}
    D -->|No| E[Attempt Reconnection]
    D -->|Yes| F[Retry with Backoff]
    E --> G{Reconnect Success?}
    G -->|Yes| F
    G -->|No| H[Alert & Exit]
    
    B -->|Order Error| I[Check Order Status]
    I --> J{Order Exists?}
    J -->|No| K[Mark as Failed]
    J -->|Yes| L[Attempt Recovery]
    L --> M{Recovery Success?}
    M -->|Yes| N[Continue]
    M -->|No| O[Force Close Position]
    
    B -->|State Error| P[Validate Against Exchange]
    P --> Q[Reconcile Differences]
    Q --> R[Update Local State]
    
    B -->|Critical Error| S[Emergency Stop]
    S --> T[Close All Positions]
    T --> U[Send Alert]
    U --> H
    
    F --> V{Retry Success?}
    V -->|Yes| N
    V -->|No| W{Max Retries?}
    W -->|Yes| H
    W -->|No| F
    
    K --> N
    O --> N
    R --> N
    N --> X[Resume Operations]
    
    style H fill:#ffebee
    style S fill:#ffebee
    style X fill:#e8f5e8
```

These flow diagrams provide a comprehensive visual representation of the dYdX Trading Bot's operational logic, from high-level execution flow to detailed state management and error handling procedures. Each diagram can be rendered using Mermaid-compatible viewers or documentation platforms.