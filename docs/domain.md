# Domain

## 1. Core Entities

- **Client** – Merchant / operator using PayCrypt (betting brand, casino, etc.).
- **Payment** – Crypto payment session (amount, currency, status, addresses, txid, etc.).
- **Withdrawal** – Outgoing payout from client balance to player wallet.
- **Wallet / WalletProvider** – Underlying crypto wallet integrations (manual, API-based, platform default).
- **BankGatewayProvider** – Bank gateway provider entity (for manual bank rails).
- **BankGatewayAccount** – Individual bank accounts managed by providers.
- **BankGatewayTransaction / DepositRequest** – Bank-side deposit/withdraw flows.

## 2. Use Cases (Examples)

- Player makes a USDT deposit to a betting platform using PayCrypt.
- Operator requests a withdrawal from client balance to a player wallet.
- Provider/admin manages bank gateway accounts and reconciles bank transfers.
- Operator inspects audit logs and login history for compliance.

Use this file to document new entities and flows as the system evolves.
