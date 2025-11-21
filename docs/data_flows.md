# Data Flows

This file is for visualising / describing how data moves through the unified system.

## 1. Crypto Deposit Flow (Summary)

- Request: API or internal call to create a `Payment` (crypto deposit).
- Processing: Wallet selection + address generation.
- Player: Sees deposit address / QR via client UI or demo gateway.
- Blockchain: Transaction is broadcast and confirmed.
- Webhook: Wallet provider or internal watcher notifies PayCrypt.
- Reconciliation: Payment status is updated; client systems update balances.

## 2. Bank Gateway Deposit Flow (Summary)

- Client site creates a bank deposit request through `/bank-api`.
- Player uploads proof / references a bank transfer.
- Provider / admin confirms or rejects via provider/admin panels.
- Commission and balances are adjusted.

Add diagrams, sequence charts, or more detailed steps here over time.
