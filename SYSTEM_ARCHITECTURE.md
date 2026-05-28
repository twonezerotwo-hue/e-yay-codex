# E-yAy / BrainChain System Architecture

## 1. Purpose

E-yAy / BrainChain is an investment decision support system that reads the world with state-like breadth, but is not a state actor. It is designed to monitor macro, credit, energy, commodity, crypto, geopolitical, and AI-grid infrastructure relationships while preserving deterministic decision control, strict validation, and execution isolation.

The system does not allow AI to make final decisions. AI explains context, summarizes evidence, and supports operator understanding. Final decision flow is governed by deterministic logic, risk controls, and validation gates.

## 2. Mission Profile

The platform is built to:
- monitor global cross-asset and cross-domain signals,
- connect macro and market regimes to infrastructure and supply-chain dependencies,
- detect risk and regime changes early,
- produce short owner-facing CEO briefings,
- log every forecast and decision path,
- review the last 7 days through a weekly learning loop,
- avoid unverified live market language when verified data is missing.

## 3. Core Design Principles

### 3.1 Decision Authority
- AI does not decide; AI explains.
- Decision Core is deterministic.
- Risk Engine is the final gate.
- Execution is OFF by default (`NO_EXECUTION`).
- `AUTO_FULL` remains disabled.

### 3.2 Validation and Integrity
- Validation-first operation is mandatory.
- News alone cannot trigger a decision.
- Technical analysis alone cannot trigger a decision.
- No live conclusion is allowed without verified data.
- Every decision must be written to audit logs.
- Source binding must connect outputs to evidence.

### 3.3 Environment Isolation
- Paper and live environments are separated.
- Execution control is isolated from interpretation and analytics.
- Kill Switch must stop the system when risk thresholds are exceeded.

## 4. Functional Scope

The system watches the interaction between:
- macro economy,
- credit stress,
- energy markets,
- commodities,
- crypto structure,
- geopolitics,
- AI infrastructure demand,
- electrical grid and industrial bottlenecks.

It is a decision support platform, not an autonomous trading engine.

## 5. Primary Monitoring Universe

### 5.1 Macro and Rates
- CPI
- PPI
- M2
- US02Y
- US10Y
- US20Y
- DXY

### 5.2 Credit and Risk Appetite
- HYG
- JNK

### 5.3 Equities and Broad Risk Assets
- Nasdaq
- QQQ
- SP500
- China equities
- FXI

### 5.4 Commodities and Metals
- Brent
- Gold
- Silver
- Copper
- XAUXAG ratio

### 5.5 Crypto Structure
- BTC
- BTC.D
- USDT.D
- TOTAL
- TOTAL2

### 5.6 AI-Grid Infrastructure Chain
- AI data centers
- electricity demand
- power grid constraints
- transformers
- switchgear
- power electronics
- conductors
- cooling chain

## 6. High-Level System Modules

### 6.1 Data Intake Layer
Responsibilities:
- ingest approved market, macro, and infrastructure data,
- track source provenance,
- timestamp all records,
- distinguish verified and unverified inputs.

### 6.2 Data Integrity Gate
Responsibilities:
- validate schema, freshness, completeness, and source trust,
- reject low-confidence or stale inputs,
- prevent downstream live interpretation when validation fails.

### 6.3 World Model Layer
Responsibilities:
- organize relationships across macro, credit, energy, commodities, crypto, geopolitics, and AI infrastructure,
- maintain regime context,
- surface linked stress channels.

### 6.4 Signal Interpretation Layer
Responsibilities:
- explain what changed,
- compare cross-market alignment or divergence,
- produce context summaries for deterministic evaluation.

AI may assist explanation here, but cannot authorize action.

### 6.5 Deterministic Decision Core
Responsibilities:
- evaluate explicit rule sets,
- combine validated signals using fixed logic,
- produce controlled decision states such as observe, caution, block, or prepare.

The Decision Core must be transparent, reproducible, and testable.

### 6.6 Risk Engine
Responsibilities:
- apply exposure, volatility, concentration, liquidity, and scenario controls,
- override any upstream recommendation when risk limits are breached,
- act as the final pre-execution gate.

### 6.7 Kill Switch
Responsibilities:
- stop decision flow into execution when hard risk conditions are met,
- halt on integrity failure, environment mismatch, or risk overshoot,
- require explicit operator recovery procedure.

### 6.8 Execution Control
Responsibilities:
- keep execution disabled by default,
- separate paper and live actions,
- prevent automatic full deployment,
- require explicit environment and policy approval before any action.

### 6.9 OwnerBrief
Responsibilities:
- generate short CEO-level summaries,
- explain regime, risks, and notable changes,
- avoid unsupported certainty,
- distinguish verified facts from interpretation.

### 6.10 Audit and Source Binding
Responsibilities:
- log every forecast, rule evaluation, and final decision state,
- bind outputs to input sources,
- support replay, review, and accountability.

### 6.11 Weekly Learning Loop
Responsibilities:
- review the most recent 7 days,
- compare forecasts with realized outcomes,
- identify rule failures, missing data, and false confidence,
- improve process without making the system non-deterministic.

## 7. Decision Policy Rules

The following policy rules are mandatory:
- AI cannot place or approve trades.
- News is insufficient as a standalone decision driver.
- Technical analysis is insufficient as a standalone decision driver.
- Unverified data cannot produce live market wording or live action states.
- The Risk Engine can block all upstream outputs.
- Audit logging is mandatory for every decision path.
- Live and paper modes must never share uncontrolled state.

## 8. Reference 23-Layer Operational Model

1. Source Registry
2. Data Connectors
3. Ingestion Scheduler
4. Raw Data Store
5. Data Integrity Gate
6. Normalization Layer
7. Time Alignment Layer
8. Provenance and Source Binding
9. Macro Signal Layer
10. Credit Signal Layer
11. Energy Signal Layer
12. Commodity Signal Layer
13. Crypto Structure Layer
14. Geopolitical Context Layer
15. AI-Grid Infrastructure Layer
16. Cross-Asset Correlation Layer
17. Regime Detection Layer
18. Deterministic Decision Core
19. Risk Engine
20. Kill Switch
21. Execution Control
22. OwnerBrief and Reporting
23. Audit, Replay, and Weekly Learning Loop

## 9. Environment and Control States

### 9.1 Default State
- execution disabled,
- live action blocked,
- validation required before any live wording,
- operator review expected.

### 9.2 Paper Mode
- simulations and paper tracking allowed,
- no live execution,
- full audit logging enabled.

### 9.3 Live Mode
- only available after explicit enablement,
- only available when validation gates pass,
- always subject to Risk Engine and Kill Switch authority.

## 10. Output Standards

All system outputs must:
- clearly separate verified facts from interpretation,
- avoid overstating confidence,
- identify missing or stale data,
- summarize risk before opportunity,
- remain short and executive-readable for owner reports.

## 11. Non-Goals

The system is not intended to:
- operate as a fully autonomous trading AI,
- bypass human oversight,
- use unverified data for live claims,
- collapse risk control into AI-generated narrative.

## 12. Initial Build Constraint

This repository starts from a clean installation.
- No legacy Kimi repositories are reused.
- No half-finished code is migrated.
- Handoff discipline is mandatory so Codex and Kimi can continue work from the same repository state.
- Architecture, state tracking, and next-task visibility are required before application code begins.
