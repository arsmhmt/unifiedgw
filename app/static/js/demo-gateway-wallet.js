(function () {
    const config = window.demoGatewayConfig || {};

    const state = {
        loggedIn: false,
        transactions: [],
        baseBalance: 0,
        balanceCurrency: 'TRY'
    };

    const api = {
        url: localStorage.getItem('demoGatewayApiUrl') || `${window.location.origin}/api/v1`,
        key: localStorage.getItem('demoGatewayApiKey') || 'demo_live_pk_xxxx'
    };

    const els = {};

    document.addEventListener('DOMContentLoaded', () => {
        cacheElements();
        bootstrapFromConfig();
        wireEvents();
        injectApiSamples();
        updateConversionPreview();
    });

    function cacheElements() {
        els.loginForm = document.getElementById('demoLoginForm');
        els.loginSuccess = document.getElementById('demoLoginSuccess');
        els.depositForm = document.getElementById('depositForm');
        els.withdrawForm = document.getElementById('withdrawForm');
        els.apiConsole = document.getElementById('apiConsole');
        els.transactions = document.getElementById('demoTransactions');
        els.balance = document.getElementById('availableBalance');
        els.copyKey = document.getElementById('copyDemoKey');
        els.clearConsole = document.getElementById('clearConsole');
        els.apiUrl = document.getElementById('demoApiUrl');
        els.apiKey = document.getElementById('demoApiKey');
        els.curlDeposit = document.getElementById('curlDeposit');
        els.fetchWithdrawal = document.getElementById('fetchWithdrawal');
        els.depositFiatAmount = document.getElementById('depositFiatAmount');
        els.depositFiatCurrency = document.getElementById('depositFiatCurrency');
        els.depositCryptoCurrency = document.getElementById('depositCryptoCurrency');
        els.depositNetwork = document.getElementById('depositNetwork');
        els.conversionPreview = document.getElementById('conversionPreview');
        els.depositDetails = document.getElementById('depositDetails');
        els.depositCryptoAmount = document.getElementById('depositCryptoAmount');
        els.depositRate = document.getElementById('depositRate');
        els.depositAddress = document.getElementById('depositAddress');
        els.depositQr = document.getElementById('depositQr');
        els.copyDepositAddress = document.getElementById('copyDepositAddress');
    }

    function wireEvents() {
        if (els.loginForm) {
            els.loginForm.addEventListener('submit', onLogin);
        }
        if (els.depositForm) {
            els.depositForm.addEventListener('submit', onDeposit);
        }
        if (els.withdrawForm) {
            els.withdrawForm.addEventListener('submit', onWithdraw);
        }
        if (els.copyKey) {
            els.copyKey.addEventListener('click', copyApiKey);
        }
        if (els.clearConsole) {
            els.clearConsole.addEventListener('click', clearConsole);
        }
        if (els.copyDepositAddress) {
            els.copyDepositAddress.addEventListener('click', copyDepositAddress);
        }
        [
            els.depositFiatAmount,
            els.depositFiatCurrency,
            els.depositCryptoCurrency,
            els.depositNetwork
        ].forEach(input => {
            if (input) {
                input.addEventListener('input', updateConversionPreview);
                input.addEventListener('change', updateConversionPreview);
            }
        });
    }

    function bootstrapFromConfig() {
        if (config.api_url) {
            api.url = config.api_url;
        }
        if (config.api_key) {
            api.key = config.api_key;
        }

        renderApiMetadata();

        const stats = config.demo_stats || {};
        if (typeof stats.demo_balance === 'number') {
            state.baseBalance = Number(stats.demo_balance);
        }
        if (stats.recent_transactions && Array.isArray(stats.recent_transactions)) {
            state.transactions = stats.recent_transactions.map(tx => ({
                type: (tx.type || '').toLowerCase(),
                fiatAmount: typeof tx.amount === 'number' ? tx.amount : null,
                fiatCurrency: tx.currency || state.balanceCurrency,
                cryptoAmount: tx.crypto_amount || null,
                cryptoCurrency: tx.crypto_currency || null,
                status: tx.status || 'approved',
                network: tx.network || null,
                created_at: tx.created_at,
                affectsBalance: false,
                source: 'history'
            }));
        }

        updateBalance();
        renderTransactions();
    }

    function renderApiMetadata() {
        if (els.apiUrl) {
            els.apiUrl.textContent = api.url;
        }
        if (els.apiKey) {
            els.apiKey.textContent = api.key;
        }
    }

    function injectApiSamples() {
        const depositPayload = {
            fiat_amount: 250,
            fiat_currency: 'TRY',
            crypto_currency: 'USDT',
            crypto_network: 'TRC20',
            client_id: config.client_id || 'demo_client_001',
            user_id: config.user_id || 'demo_user_001'
        };

        if (els.curlDeposit) {
            els.curlDeposit.textContent = `curl -X POST \
  '${api.url}/crypto/deposits' \
  -H 'Authorization: Bearer ${api.key}' \
  -H 'Content-Type: application/json' \
  -d '${JSON.stringify(depositPayload, null, 2)}'`;
        }

        if (els.fetchWithdrawal) {
            els.fetchWithdrawal.textContent = `fetch('${api.url}/crypto/withdrawals', {
  method: 'POST',
  headers: {
    'Authorization': 'Bearer ${api.key}',
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    amount: 120,
    crypto_network: 'TRC20',
    wallet_address: 'TByDemoWalletAddress123',
    client_id: 'demo_client_001',
    user_id: 'demo_user_001'
  })
}).then(res => res.json()).then(console.log);`;
        }
    }

    function onLogin(evt) {
        evt.preventDefault();
        state.loggedIn = true;
        els.loginSuccess.classList.remove('d-none');
        toast('Demo session activated.');
        persistConfig();
    }

    function persistConfig() {
        localStorage.setItem('demoGatewayApiUrl', api.url);
        localStorage.setItem('demoGatewayApiKey', api.key);
    }

    async function onDeposit(evt) {
        evt.preventDefault();
        if (!requireLogin()) return;

        const fiatAmount = parseFloat((els.depositFiatAmount && els.depositFiatAmount.value) || '0');
        const fiatCurrency = (els.depositFiatCurrency && els.depositFiatCurrency.value) || 'TRY';
        const cryptoCurrency = (els.depositCryptoCurrency && els.depositCryptoCurrency.value) || 'USDT';
        const network = (els.depositNetwork && els.depositNetwork.value) || 'TRC20';

        if (!fiatAmount || fiatAmount <= 0) {
            toast('Enter a valid fiat amount.', 'warning');
            return;
        }

        const payload = {
            fiat_amount: fiatAmount,
            fiat_currency: fiatCurrency,
            crypto_currency: cryptoCurrency,
            crypto_network: network,
            client_id: config.client_id || 'demo_client_001',
            user_id: config.user_id || 'demo_user_001'
        };

        const data = await callApi('/crypto/deposits', payload, 'Deposit created');
        if (!data) return;

        showDepositDetails(data);
        addTransaction({
            type: 'deposit',
            fiatAmount,
            fiatCurrency,
            cryptoAmount: data.crypto_amount,
            cryptoCurrency: data.crypto_currency,
            status: data.status || 'pending',
            network,
            created_at: data.created_at || new Date().toISOString(),
            affectsBalance: false,
            source: 'session'
        });
    }

    async function onWithdraw(evt) {
        evt.preventDefault();
        if (!requireLogin()) return;

        const amount = parseFloat(document.getElementById('withdrawAmount').value || '0');
        const network = document.getElementById('withdrawNetwork').value;
        const wallet = document.getElementById('withdrawWallet').value;

        const payload = {
            amount,
            crypto_network: network,
            wallet_address: wallet,
            client_id: config.client_id || 'demo_client_001',
            user_id: config.user_id || 'demo_user_001'
        };

        const data = await callApi('/crypto/withdrawals', payload, 'Withdrawal submitted');
        addTransaction({
            type: 'withdrawal',
            amount,
            currency: 'USDT',
            status: data?.status || 'pending',
            network,
            created_at: new Date().toISOString()
        });
    }

    async function callApi(path, payload, successMessage) {
        try {
            logToConsole({ request: { path, payload } });
            const response = await fetch(`${api.url}${path}`, {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${api.key}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(payload)
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || data.message || response.statusText);
            }

            logToConsole(data, true);
            toast(successMessage || 'Request successful.');
            return data;
        } catch (err) {
            toast(err.message || 'Request failed', 'danger');
            logToConsole({ error: err.message || String(err) }, false);
        }
    }

    function addTransaction(tx) {
        state.transactions.unshift(tx);
        state.transactions = state.transactions.slice(0, 6);
        renderTransactions();
        updateBalance();
    }

    function renderTransactions() {
        if (!els.transactions) return;
        if (!state.transactions.length) {
            els.transactions.innerHTML = '<p class="mb-0">No transactions yet.</p>';
            return;
        }

        const rows = state.transactions.map(tx => `
            <div class="d-flex align-items-center justify-content-between border-bottom border-secondary py-2">
                <div>
                    <span class="badge ${tx.type === 'deposit' ? 'bg-success' : 'bg-warning text-dark'} text-uppercase me-2">${tx.type}</span>
                    <span class="text-white-50">${formatTimestamp(tx.created_at)}</span>
                </div>
                <div class="text-end">
                    <div class="fw-semibold text-white">${renderPrimaryAmount(tx)}</div>
                    <small class="text-muted">${renderTransactionMeta(tx)}</small>
                </div>
            </div>
        `);

        els.transactions.innerHTML = rows.join('');
    }

    function updateBalance() {
        if (!els.balance) return;
        const adjustments = state.transactions.reduce((sum, tx) => {
            if (!tx.affectsBalance) return sum;
            const sign = tx.type === 'deposit' ? 1 : -1;
            const amount = typeof tx.fiatAmount === 'number' ? tx.fiatAmount : (typeof tx.amount === 'number' ? tx.amount : 0);
            return sum + sign * amount;
        }, 0);
        const balance = state.baseBalance + adjustments;
        els.balance.textContent = formatCurrency(balance, state.balanceCurrency);
    }

    function logToConsole(data, success = true) {
        if (!els.apiConsole) return;
        const timestamp = new Date().toLocaleTimeString();
        const entry = {
            timestamp,
            success,
            data
        };
        const existing = els.apiConsole.textContent.trim();
        const log = existing && existing !== '{}' ? JSON.parse(existing) : [];
        log.unshift(entry);
        els.apiConsole.textContent = JSON.stringify(log.slice(0, 5), null, 2);
    }

    function clearConsole() {
        if (els.apiConsole) {
            els.apiConsole.textContent = '{}';
        }
    }

    function copyApiKey(evt) {
        evt.preventDefault();
        navigator.clipboard.writeText(api.key)
            .then(() => toast('Demo API key copied.'))
            .catch(() => toast('Unable to copy key', 'danger'));
    }

    function copyDepositAddress(evt) {
        evt.preventDefault();
        if (!els.depositAddress) return;
        const address = els.depositAddress.textContent.trim();
        if (!address) return;
        navigator.clipboard.writeText(address)
            .then(() => toast('Deposit address copied.'))
            .catch(() => toast('Unable to copy address', 'danger'));
    }

    function requireLogin() {
        if (!state.loggedIn) {
            toast('Activate the demo session by logging in first.', 'warning');
            return false;
        }
        return true;
    }

    function showDepositDetails(data) {
        if (!els.depositDetails) return;
        els.depositDetails.classList.remove('d-none');

        if (els.depositCryptoAmount) {
            const cryptoAmount = typeof data.crypto_amount === 'number' ? data.crypto_amount : parseFloat(data.crypto_amount || '0');
            const formattedCrypto = Number.isFinite(cryptoAmount) ? `${cryptoAmount.toFixed(8)} ${data.crypto_currency}` : `${data.crypto_amount} ${data.crypto_currency}`;
            els.depositCryptoAmount.textContent = formattedCrypto;
        }
        if (els.depositRate) {
            const rate = Number(data.exchange_rate || 0).toFixed(4);
            els.depositRate.textContent = `Rate: 1 ${data.crypto_currency} ≈ ${rate} ${data.fiat_currency}`;
        }
        if (els.depositAddress) {
            els.depositAddress.textContent = data.deposit_address || '';
        }
        if (els.depositQr) {
            if (data.qr_code) {
                els.depositQr.innerHTML = `<img src="${data.qr_code}" alt="Deposit QR" class="img-fluid" />`;
            } else {
                els.depositQr.textContent = 'QR code unavailable';
            }
        }
    }

    function updateConversionPreview() {
        if (!els.conversionPreview) return;
        const amount = parseFloat((els.depositFiatAmount && els.depositFiatAmount.value) || '0');
        const fiatCurrency = (els.depositFiatCurrency && els.depositFiatCurrency.value) || 'TRY';
        const cryptoCurrency = (els.depositCryptoCurrency && els.depositCryptoCurrency.value) || 'USDT';
        const network = (els.depositNetwork && els.depositNetwork.value) || 'TRC20';

        if (!amount || amount <= 0) {
            els.conversionPreview.innerHTML = '<div class="small text-muted">Enter amount to see conversion summary</div>';
            return;
        }

        els.conversionPreview.innerHTML = `
            <div>
                <div class="fw-semibold text-white">${formatCurrency(amount, fiatCurrency)}</div>
                <small class="text-muted">Converted to ${cryptoCurrency} on ${network}</small>
            </div>
        `;
    }

    function renderPrimaryAmount(tx) {
        if (typeof tx.fiatAmount === 'number') {
            const sign = tx.type === 'deposit' ? '+' : '-';
            return `${sign}${formatCurrency(Math.abs(tx.fiatAmount), tx.fiatCurrency || state.balanceCurrency)}`;
        }
        if (typeof tx.amount === 'number') {
            const sign = tx.type === 'deposit' ? '+' : '-';
            return `${sign}${tx.amount.toFixed(2)} ${tx.currency || 'USDT'}`;
        }
        return '—';
    }

    function renderTransactionMeta(tx) {
        const meta = [];
        if (typeof tx.cryptoAmount === 'number' && tx.cryptoCurrency) {
            meta.push(`${tx.cryptoAmount.toFixed(8)} ${tx.cryptoCurrency}`);
        }
        if (tx.status) {
            meta.push(tx.status);
        }
        if (tx.network) {
            meta.push(tx.network);
        }
        return meta.join(' · ');
    }

    function formatTimestamp(value) {
        if (!value) return '—';
        const date = new Date(value);
        if (!Number.isFinite(date.getTime())) return value;
        return date.toLocaleString();
    }

    function formatCurrency(amount, currency) {
        const formatter = new Intl.NumberFormat(undefined, {
            style: 'currency',
            currency: currency || 'TRY',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });
        return formatter.format(Number(amount || 0));
    }

    function toast(message, variant = 'success') {
        if (!window.bootstrap || !document.body) {
            alert(message);
            return;
        }

        const toastEl = document.createElement('div');
        toastEl.className = `toast align-items-center text-bg-${variant} border-0`;
        toastEl.role = 'alert';
        toastEl.innerHTML = `
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>`;

        let container = document.getElementById('toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'toast-container';
            container.className = 'position-fixed bottom-0 end-0 p-3';
            container.style.zIndex = 1080;
            document.body.appendChild(container);
        }

        container.appendChild(toastEl);
        const bsToast = new bootstrap.Toast(toastEl, { delay: 3000 });
        bsToast.show();
    }
})();
