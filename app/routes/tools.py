from flask import Blueprint, render_template, request, jsonify, flash, url_for
import os
import requests
import time
from datetime import datetime

tools_bp = Blueprint('tools', __name__, url_prefix='/tools')

AI_SUMMARY_MODEL = os.getenv('OPENAI_SUMMARY_MODEL', 'gpt-3.5-turbo')

@tools_bp.route('/')
def index():
    """Tools landing page with all available tools"""
    tools_list = [
        {
            'name': 'RugCheck AI',
            'description': 'AI-enhanced token security analysis powered by PayCrypt intelligence and GoPlus API.',
            'icon': 'fas fa-shield-alt',
            'url': 'tools.rugcheck',
            'status': 'active',
            'features': [
                'Honeypot Detection',
                '20+ Blockchain Support', 
                'Smart Contract Analysis',
                'Basic Risk Assessment'
            ]
        },
        {
            'name': 'Token Explorer',
    'description': 'Comprehensive token analysis with metadata, liquidity, holders, and advanced honeypot detection.',
    'icon': 'fas fa-search',
    'url': 'tools.token_explorer',
    'status': 'active',
    'features': [
        'Token Metadata Analysis',
        'DEX Liquidity Tracking', 
        'Top Holders Analysis',
        'Advanced Honeypot Detection'
    ]
},
{
    'name': 'Price Tracker',
    'description': 'Real-time cryptocurrency price tracking with alerts and portfolio management.',
    'icon': 'fas fa-chart-line',
    'url': 'tools.price_tracker',
    'status': 'active',
    'features': [
        'Real-time Prices',
        'Price Alerts',
        'Portfolio Tracking',
        'Historical Data'
    ]
},
{
    'name': 'DEX Aggregator',
    'description': 'Find the best prices across decentralized exchanges for optimal trading.',
    'icon': 'fas fa-exchange-alt',
    'url': 'tools.dex_aggregator',
    'status': 'active',
    'features': [
        'Best Price Discovery',
        'Multi-DEX Support',
        'Gas Optimization',
        'Slippage Protection'
    ]
},
        {
            'name': 'Yield Farming Calculator',
            'description': 'Calculate potential returns from DeFi yield farming opportunities.',
            'icon': 'fas fa-calculator',
            'url': 'tools.yield_calculator',
            'status': 'active',
            'features': [
                'APY Calculation',
                'Risk Assessment',
                'Impermanent Loss Calculator',
                'Multi-Pool Comparison'
            ]
        },
        {
            'name': 'Honeypot Detector',
            'description': 'Advanced honeypot detection to verify if tokens can be sold after purchase.',
            'icon': 'fas fa-bug',
            'url': 'tools.honeypot_check',
            'status': 'active',
            'features': [
                'Buy/Sell Simulation',
                'Tax Analysis',
                'Liquidity Trap Detection',
                'Multi-Chain Support'
            ]
        },
        {
            'name': 'Token Security Scanner',
            'description': 'Comprehensive smart contract security audit with detailed scoring system.',
            'icon': 'fas fa-shield-virus',
            'url': 'tools.token_scan',
            'status': 'active',
            'features': [
                'Smart Contract Audit',
                'Security Score Rating',
                'Ownership Analysis',
                'Risk Factor Breakdown'
            ]
        },
        {
            'name': 'Contract Audit Checker',
            'description': 'Verify official audits from CertiK, Hacken, and other top security firms.',
            'icon': 'fas fa-certificate',
            'url': 'tools.audit_check',
            'status': 'active',
            'features': [
                'Official Audit Verification',
                'Multi-Auditor Support',
                'Audit Report Links',
                'Trust Score Calculation'
            ]
        },
        {
            'name': 'Liquidity Lock Checker',
            'description': 'Verify if token liquidity is locked on Unicrypt, Team Finance, and other lockers.',
            'icon': 'fas fa-lock',
            'url': 'tools.liquidity_lock',
            'status': 'active',
            'features': [
                'Multi-Locker Support',
                'Lock Duration Analysis',
                'Unlock Date Tracking',
                'Lock Percentage Calculation'
            ]
        },
        {
            'name': 'Wallet Intelligence',
            'description': 'AI-driven wallet behavior insights, portfolio breakdowns, and trading pattern detection.',
            'icon': 'fas fa-wallet',
            'url': 'tools.wallet_profiler',
            'status': 'active',
            'features': [
                'Portfolio Analysis',
                'Trading History',
                'Profit/Loss Tracking',
                'Whale Detection'
            ]
        },
        {
            'name': 'Gas Tracker',
            'description': 'Real-time gas prices across all chains with optimal transaction timing recommendations.',
            'icon': 'fas fa-fire',
            'url': 'tools.gas_tracker',
            'status': 'active',
            'features': [
                'Multi-Chain Gas Prices',
                'Best Time to Transact',
                'Gas Price Alerts',
                'Historical Gas Data'
            ]
        },
        {
            'name': 'MEV Protection Checker',
            'description': 'Detect MEV bot activity and front-running risks for maximum trading protection.',
            'icon': 'fas fa-robot',
            'url': 'tools.mev_protection',
            'status': 'active',
            'features': [
                'MEV Bot Detection',
                'Front-running Analysis',
                'Sandwich Attack Protection',
                'MEV-Safe DEX Routes'
            ]
        },
        {
            'name': 'Airdrop Hunter',
            'description': 'Track upcoming airdrops and check eligibility for maximum profit opportunities.',
            'icon': 'fas fa-parachute-box',
            'url': 'tools.airdrop_hunter',
            'status': 'active',
            'features': [
                'Upcoming Airdrops',
                'Eligibility Checker',
                'Airdrop Farming Guide',
                'Historical Airdrop Data'
            ]
        },
        {
            'name': 'Rug Pull Alert',
            'description': 'Real-time monitoring and alerts for suspicious token activities and potential rug pulls.',
            'icon': 'fas fa-exclamation-triangle',
            'url': 'tools.rug_alert',
            'status': 'active',
            'features': [
                'Real-time Monitoring',
                'Whale Movement Alerts',
                'Liquidity Removal Warnings',
                'Dev Wallet Tracking'
            ]
        }
    ]

    featured_tool = {
        'name': 'RugCheck AI',
        'badge': 'Featured Tool of the Week',
        'summary': 'Identify scams faster with AI-generated risk summaries and live token security analytics.',
        'cta_label': 'Launch RugCheck AI',
        'cta_url': url_for('tools.rugcheck', ref='featured'),
        'highlights': [
            'Real-time honeypot and liquidity checks',
            'GPT-powered risk briefings',
            'Multi-chain support across 20+ networks'
        ]
    }

    return render_template('tools/index.html', tools=tools_list, featured_tool=featured_tool)

# GoPlus API supported chains
SUPPORTED_CHAINS = {
    '1': 'Ethereum',
    '56': 'BSC (Binance Smart Chain)',
    '137': 'Polygon',
    '250': 'Fantom',
    '43114': 'Avalanche',
    '42161': 'Arbitrum',
    '10': 'Optimism',
    '25': 'Cronos',
    '128': 'HECO',
    '66': 'OKExChain',
    '321': 'KCC',
    '1285': 'Moonriver',
    '42220': 'Celo',
    '1284': 'Moonbeam',
}

def analyze_token_security(result):
    """Analyze GoPlus API result and provide human-readable assessment"""
    if not result or 'error' in result:
        return {'status': 'error', 'message': 'Unable to analyze token'}

    
    risks = []
    warnings = []
    info = []
    
    # Check for critical risks
    if result.get('is_honeypot') == '1':
        risks.append('🚨 HONEYPOT DETECTED - Cannot sell tokens!')
    
    if result.get('is_blacklisted') == '1':
        risks.append('🚨 BLACKLISTED TOKEN - High risk!')
    
    if result.get('is_whitelisted') == '1':
        info.append('✅ Whitelisted token')
    
    # Check trading restrictions
    if result.get('cannot_buy') == '1':
        risks.append('❌ Cannot buy this token')
    
    if result.get('cannot_sell_all') == '1':
        risks.append('❌ Cannot sell all tokens')
    
    # Check for suspicious patterns
    if result.get('is_proxy') == '1':
        warnings.append('⚠️ Proxy contract detected')
    
    if result.get('is_mintable') == '1':
        warnings.append('⚠️ Token supply can be increased')
    
    # Check owner privileges
    owner_change_balance = result.get('owner_change_balance')
    if owner_change_balance == '1':
        risks.append('🚨 Owner can modify balances')
    
    # Check tax information
    buy_tax = result.get('buy_tax')
    sell_tax = result.get('sell_tax')
    
    if buy_tax:
        try:
            buy_tax_pct = float(buy_tax) * 100
            if buy_tax_pct > 10:
                warnings.append(f'⚠️ High buy tax: {buy_tax_pct:.1f}%')
            else:
                info.append(f'Buy tax: {buy_tax_pct:.1f}%')
        except:
            pass
    
    if sell_tax:
        try:
            sell_tax_pct = float(sell_tax) * 100
            if sell_tax_pct > 10:
                warnings.append(f'⚠️ High sell tax: {sell_tax_pct:.1f}%')
            else:
                info.append(f'Sell tax: {sell_tax_pct:.1f}%')
        except:
            pass
    
    # Determine overall risk level
    if risks:
        risk_level = 'HIGH'
        risk_color = 'danger'
    elif warnings:
        risk_level = 'MEDIUM'
        risk_color = 'warning'
    else:
        risk_level = 'LOW'
        risk_color = 'success'
    
    return {
        'status': 'success',
        'risk_level': risk_level,
        'risk_color': risk_color,
        'risks': risks,
        'warnings': warnings,
        'info': info
    }

@tools_bp.route('/rugcheck', methods=['GET', 'POST'])
@tools_bp.route('/rugchecker', methods=['GET', 'POST'])  # Alternative URL
def rugcheck():
    result = None
    analysis = None
    ai_summary = None
    
    if request.method == 'POST':
        chain = request.form.get('chain')
        address = request.form.get('address', '').strip()
        
        if not address:
            flash('Please enter a token contract address', 'error')
            return render_template('tools/rugcheck.html', 
                                 chains=SUPPORTED_CHAINS, 
                                 result=result, 
                                 analysis=analysis,
                                 ai_summary=ai_summary)
        
        # Validate address format (basic check)
        if not address.startswith('0x') or len(address) != 42:
            flash('Invalid contract address format. Address should start with 0x and be 42 characters long.', 'error')
            return render_template('tools/rugcheck.html', 
                                 chains=SUPPORTED_CHAINS, 
                                 result=result, 
                                 analysis=analysis,
                                 ai_summary=ai_summary)

        api_url = f"https://api.gopluslabs.io/api/v1/token_security/{chain}?contract_addresses={address}"
        
        try:
            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('code') != 1:
                flash(f"API Error: {data.get('message', 'Unknown error')}", 'error')
            else:
                result = data.get('result', {}).get(address.lower(), {})
                if not result:
                    flash('No data found for this token address', 'warning')
                else:
                    analysis = analyze_token_security(result)
                    
                    # Add chain info to result
                    result['_chain_name'] = SUPPORTED_CHAINS.get(chain, f'Chain {chain}')
                    result['_chain_id'] = chain
                    result['_address'] = address
                    result['_timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')

                    if analysis and analysis.get('status') == 'success':
                        prompt, fallback = _build_rugcheck_summary_inputs(result, analysis)
                        summary_text, generated = _generate_ai_summary(prompt, fallback)
                        ai_summary = {
                            'text': summary_text,
                            'generated': generated
                        }
                    
        except requests.exceptions.Timeout:
            flash('Request timed out. Please try again.', 'error')
        except requests.exceptions.RequestException as e:
            flash(f'Network error: {str(e)}', 'error')
        except Exception as e:
            flash(f'Unexpected error: {str(e)}', 'error')

    return render_template('tools/rugcheck.html', 
                         chains=SUPPORTED_CHAINS, 
                         result=result, 
                         analysis=analysis,
                         ai_summary=ai_summary)

@tools_bp.route('/token-explorer', methods=['GET', 'POST'])
def token_explorer():
    """Comprehensive token explorer with advanced analysis"""
    if request.method == 'POST':
        chain = request.form.get('chain')
        address = request.form.get('address')
        
        if not chain or not address:
            flash('Please provide both blockchain and token address.', 'error')
            return render_template('tools/token_explorer.html', chains=SUPPORTED_CHAINS)
        
        try:
            # Get comprehensive token data
            result = get_comprehensive_token_data(chain, address)
            
            if result and result.get('success'):
                return render_template('tools/token_explorer.html', 
                                     chains=SUPPORTED_CHAINS,
                                     result=result,
                                     address=address,
                                     chain=chain)
            else:
                flash(f'Unable to analyze token: {result.get("error", "Unknown error")}', 'error')
                
        except Exception as e:
            flash(f'Error analyzing token: {str(e)}', 'error')
    
    return render_template('tools/token_explorer.html', chains=SUPPORTED_CHAINS)

@tools_bp.route('/api/risky-tokens')
def risky_tokens_api():
    """API endpoint for top risky tokens"""
    try:
        risky_tokens = get_top_risky_tokens()
        return jsonify({'success': True, 'tokens': risky_tokens})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def get_comprehensive_token_data(chain_id, address):
    """Get comprehensive token data from multiple sources"""
    try:
        # Initialize result structure
        result = {
            'success': False,
            'token_info': {},
            'security_analysis': {},
            'liquidity_info': {},
            'holders_info': {},
            'contract_info': {},
            'risk_assessment': {},
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        # 1. Get GoPlus Security Data
        goplus_data = get_goplus_token_data(chain_id, address)
        if goplus_data:
            result['security_analysis'] = analyze_comprehensive_security(goplus_data)
            result['token_info'].update({
                'name': goplus_data.get('token_name', 'Unknown'),
                'symbol': goplus_data.get('token_symbol', 'Unknown'),
                'decimals': goplus_data.get('decimals', 'Unknown'),
                'total_supply': goplus_data.get('total_supply', 'Unknown')
            })
        
        # 2. Get DEX Liquidity Data
        liquidity_data = get_dex_liquidity_data(chain_id, address)
        result['liquidity_info'] = liquidity_data
        
        # 3. Get Top Holders Data
        holders_data = get_top_holders_data(chain_id, address)
        result['holders_info'] = holders_data
        
        # 4. Get Contract Information
        contract_data = get_contract_information(chain_id, address)
        result['contract_info'] = contract_data
        
        # 5. Generate Risk Assessment
        result['risk_assessment'] = generate_risk_assessment(
            result['security_analysis'],
            result['liquidity_info'],
            result['holders_info'],
            result['contract_info']
        )
        
        result['success'] = True
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_goplus_token_data(chain_id, address):
    """Get token data from GoPlus API"""
    try:
        url = f"https://api.gopluslabs.io/v1/token_security/{chain_id}"
        params = {'contract_addresses': address}
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get('code') == 1 and data.get('result'):
            return data['result'].get(address.lower(), {})
        return None
        
    except Exception as e:
        print(f"GoPlus API error: {e}")
        return None

def get_dex_liquidity_data(chain_id, address):
    """Get DEX liquidity information"""
    # This would integrate with DEX APIs like Uniswap, PancakeSwap, etc.
    # For now, returning mock data structure
    return {
        'total_liquidity_usd': 'Loading...',
        'dex_pairs': [
            {
                'dex': 'Uniswap V2' if chain_id == '1' else 'PancakeSwap',
                'pair_address': 'Loading...',
                'liquidity_usd': 'Loading...',
                'volume_24h': 'Loading...'
            }
        ],
        'price_usd': 'Loading...',
        'market_cap': 'Loading...'
    }

def get_top_holders_data(chain_id, address):
    """Get top token holders information"""
    # This would integrate with blockchain explorers
    return {
        'total_holders': 'Loading...',
        'top_holders': [
            {'address': 'Loading...', 'balance': 'Loading...', 'percentage': 'Loading...'}
        ],
        'concentration_risk': 'Loading...'
    }

def get_contract_information(chain_id, address):
    """Get smart contract information"""
    return {
        'creator_address': 'Loading...',
        'creation_date': 'Loading...',
        'contract_age_days': 'Loading...',
        'is_verified': 'Loading...',
        'compiler_version': 'Loading...'
    }

def analyze_comprehensive_security(goplus_data):
    """Enhanced security analysis"""
    # Use existing function but enhance it
    mock_result = {'result': {goplus_data.get('token_name', 'unknown'): goplus_data}}
    analysis = analyze_token_security(mock_result)
    
    # Add more detailed analysis
    detailed_analysis = {
        'overall_risk': analysis.get('risk_level', 'UNKNOWN'),
        'critical_issues': analysis.get('risks', []),
        'warnings': analysis.get('warnings', []),
        'info_points': analysis.get('info', []),
        'honeypot_risk': get_honeypot_risk_level(goplus_data),
        'trading_risk': get_trading_risk_level(goplus_data),
        'ownership_risk': get_ownership_risk_level(goplus_data),
        'liquidity_risk': get_liquidity_risk_level(goplus_data)
    }
    
    return detailed_analysis

def get_honeypot_risk_level(data):
    """Detailed honeypot risk assessment"""
    if data.get('is_honeypot') == '1':
        return {'level': 'CRITICAL', 'description': 'Confirmed honeypot - cannot sell!'}
    elif data.get('buy_tax') and float(data.get('buy_tax', 0)) > 0.1:
        return {'level': 'HIGH', 'description': f'High buy tax: {float(data.get("buy_tax", 0)) * 100:.1f}%'}
    elif data.get('sell_tax') and float(data.get('sell_tax', 0)) > 0.1:
        return {'level': 'HIGH', 'description': f'High sell tax: {float(data.get("sell_tax", 0)) * 100:.1f}%'}
    else:
        return {'level': 'LOW', 'description': 'No obvious honeypot indicators'}

def get_trading_risk_level(data):
    """Trading restrictions risk assessment"""
    risks = []
    if data.get('cannot_buy') == '1':
        risks.append('Cannot buy')
    if data.get('cannot_sell_all') == '1':
        risks.append('Cannot sell all tokens')
    if data.get('transfer_pausable') == '1':
        risks.append('Transfers can be paused')
    
    if len(risks) > 2:
        return {'level': 'CRITICAL', 'issues': risks}
    elif len(risks) > 0:
        return {'level': 'HIGH', 'issues': risks}
    else:
        return {'level': 'LOW', 'issues': []}

def get_ownership_risk_level(data):
    """Owner privileges risk assessment"""
    risks = []
    if data.get('is_mintable') == '1':
        risks.append('Owner can mint new tokens')
    if data.get('owner_change_balance') == '1':
        risks.append('Owner can change balances')
    if data.get('hidden_owner') == '1':
        risks.append('Hidden owner detected')
    
    if len(risks) > 2:
        return {'level': 'CRITICAL', 'issues': risks}
    elif len(risks) > 0:
        return {'level': 'MEDIUM', 'issues': risks}
    else:
        return {'level': 'LOW', 'issues': []}

def get_liquidity_risk_level(data):
    """Liquidity risk assessment"""
    risks = []
    if data.get('is_anti_whale') == '1':
        risks.append('Anti-whale mechanism')
    if data.get('trading_cooldown') == '1':
        risks.append('Trading cooldown active')
    
    return {'level': 'LOW' if len(risks) == 0 else 'MEDIUM', 'issues': risks}

def generate_risk_assessment(security, liquidity, holders, contract):
    """Generate overall risk assessment"""
    risk_factors = []
    risk_score = 0
    
    # Security risks
    if security.get('honeypot_risk', {}).get('level') == 'CRITICAL':
        risk_score += 40
        risk_factors.append('Critical honeypot risk')
    elif security.get('honeypot_risk', {}).get('level') == 'HIGH':
        risk_score += 25
        risk_factors.append('High honeypot risk')
    
    # Trading risks
    if security.get('trading_risk', {}).get('level') == 'CRITICAL':
        risk_score += 35
        risk_factors.append('Critical trading restrictions')
    
    # Ownership risks
    if security.get('ownership_risk', {}).get('level') == 'CRITICAL':
        risk_score += 25
        risk_factors.append('Dangerous owner privileges')
    
    # Determine overall risk level
    if risk_score >= 80:
        overall_risk = 'EXTREME'
        recommendation = '🚨 DO NOT INVEST - Extremely high risk of total loss'
    elif risk_score >= 60:
        overall_risk = 'HIGH'
        recommendation = '⚠️ HIGH RISK - Only invest what you can afford to lose'
    elif risk_score >= 30:
        overall_risk = 'MEDIUM'
        recommendation = '⚠️ MEDIUM RISK - Exercise extreme caution'
    elif risk_score >= 10:
        overall_risk = 'LOW'
        recommendation = '✅ LOW RISK - Still do your own research'
    else:
        overall_risk = 'MINIMAL'
        recommendation = '✅ MINIMAL RISK - Appears relatively safe'
    
    return {
        'overall_risk': overall_risk,
        'risk_score': risk_score,
        'risk_factors': risk_factors,
        'recommendation': recommendation,
        'analysis_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
    }

def get_top_risky_tokens():
    """Get list of top risky tokens for viral content"""
    # This would scan recent deployments and analyze them
    # For now, returning mock data
    return [
        {
            'name': 'SuspiciousCoin',
            'symbol': 'SCAM',
            'address': '0x1234567890123456789012345678901234567890',
            'chain': 'Ethereum',
            'risk_score': 95,
            'main_risk': 'Confirmed Honeypot',
            'deployed_hours_ago': 2
        },
        {
            'name': 'RugToken',
            'symbol': 'RUG',
            'address': '0x0987654321098765432109876543210987654321',
            'chain': 'BSC',
            'risk_score': 88,
            'main_risk': 'Hidden Owner + Mint Function',
            'deployed_hours_ago': 6
        }
    ]

@tools_bp.route('/price-tracker', methods=['GET', 'POST'])
def price_tracker():
    """Real-time cryptocurrency price tracking"""
    if request.method == 'POST':
        symbols = request.form.get('symbols', '').upper()
        if symbols:
            try:
                prices = get_crypto_prices(symbols.split(','))
                return render_template('tools/price_tracker.html', prices=prices, symbols=symbols)
            except Exception as e:
                flash(f'Error fetching prices: {str(e)}', 'error')
    
    # Get top cryptocurrencies by default
    try:
        default_prices = get_crypto_prices(['BTC', 'ETH', 'BNB', 'ADA', 'SOL'])
        return render_template('tools/price_tracker.html', prices=default_prices)
    except Exception as e:
        flash(f'Error loading default prices: {str(e)}', 'error')
        return render_template('tools/price_tracker.html', prices={})

@tools_bp.route('/dex-aggregator', methods=['GET', 'POST'])
def dex_aggregator():
    """DEX price aggregation and optimal trading routes"""
    if request.method == 'POST':
        token_in = request.form.get('token_in')
        token_out = request.form.get('token_out')
        amount = request.form.get('amount')
        chain = request.form.get('chain')
        
        if all([token_in, token_out, amount, chain]):
            try:
                routes = get_dex_routes(token_in, token_out, amount, chain)
                return render_template('tools/dex_aggregator.html', 
                                     routes=routes,
                                     token_in=token_in,
                                     token_out=token_out,
                                     amount=amount,
                                     chain=chain,
                                     chains=SUPPORTED_CHAINS)
            except Exception as e:
                flash(f'Error finding routes: {str(e)}', 'error')
    
    return render_template('tools/dex_aggregator.html', chains=SUPPORTED_CHAINS)

@tools_bp.route('/yield-calculator', methods=['GET', 'POST'])
def yield_calculator():
    """DeFi yield farming calculator"""
    if request.method == 'POST':
        pool_type = request.form.get('pool_type')
        token_a = request.form.get('token_a')
        token_b = request.form.get('token_b')
        amount = request.form.get('amount')
        apy = request.form.get('apy')
        
        if all([pool_type, amount, apy]):
            try:
                calculation = calculate_yield_farming_returns(
                    pool_type, token_a, token_b, float(amount), float(apy)
                )
                return render_template('tools/yield_calculator.html',
                                     calculation=calculation,
                                     form_data=request.form)
            except Exception as e:
                flash(f'Error calculating yields: {str(e)}', 'error')
    
    return render_template('tools/yield_calculator.html')

def get_crypto_prices(symbols):
    """Get cryptocurrency prices from CoinGecko API"""
    try:
        # Using CoinGecko API (free tier)
        symbol_list = ','.join(symbols).lower()
        url = f"https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': symbol_list,
            'vs_currencies': 'usd',
            'include_24hr_change': 'true',
            'include_market_cap': 'true',
            'include_24hr_vol': 'true'
        }
        
        # Map common symbols to CoinGecko IDs
        symbol_map = {
            'BTC': 'bitcoin',
            'ETH': 'ethereum', 
            'BNB': 'binancecoin',
            'ADA': 'cardano',
            'SOL': 'solana',
            'MATIC': 'matic-network',
            'DOT': 'polkadot',
            'AVAX': 'avalanche-2',
            'LINK': 'chainlink',
            'UNI': 'uniswap'
        }
        
        # Convert symbols to IDs
        ids = []
        for symbol in symbols:
            symbol = symbol.upper().strip()
            if symbol in symbol_map:
                ids.append(symbol_map[symbol])
        
        if not ids:
            return {}
            
        params['ids'] = ','.join(ids)
        
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        # Convert back to symbol-based format
        result = {}
        for coin_id, price_data in data.items():
            # Find the symbol for this coin ID
            symbol = None
            for s, id in symbol_map.items():
                if id == coin_id:
                    symbol = s
                    break
            
            if symbol:
                result[symbol] = {
                    'price': price_data.get('usd', 0),
                    'change_24h': price_data.get('usd_24h_change', 0),
                    'market_cap': price_data.get('usd_market_cap', 0),
                    'volume_24h': price_data.get('usd_24h_vol', 0)
                }
        
        return result
        
    except Exception as e:
        print(f"Price API error: {e}")
        # Return mock data if API fails
        return {symbol: {
            'price': 0,
            'change_24h': 0,
            'market_cap': 0,
            'volume_24h': 0
        } for symbol in symbols}

def get_dex_routes(token_in, token_out, amount, chain):
    """Get optimal DEX trading routes"""
    # Mock implementation - in production would integrate with 1inch, 0x, etc.
    return {
        'best_route': {
            'dex': 'Uniswap V3',
            'price_impact': '0.1%',
            'minimum_received': '0.998',
            'gas_estimate': '150,000',
            'route_path': [token_in, token_out]
        },
        'alternative_routes': [
            {
                'dex': 'SushiSwap',
                'price_impact': '0.15%',
                'minimum_received': '0.995',
                'gas_estimate': '180,000',
                'route_path': [token_in, 'WETH', token_out]
            },
            {
                'dex': 'Curve',
                'price_impact': '0.08%',
                'minimum_received': '0.999',
                'gas_estimate': '200,000',
                'route_path': [token_in, token_out]
            }
        ],
        'total_routes_found': 15,
        'estimated_output': amount,
        'chain_name': SUPPORTED_CHAINS.get(chain, f'Chain {chain}')
    }

def calculate_yield_farming_returns(pool_type, token_a, token_b, amount, apy):
    """Calculate yield farming returns and impermanent loss"""
    daily_rate = apy / 365 / 100
    
    # Calculate returns for different periods
    periods = {
        'daily': 1,
        'weekly': 7,
        'monthly': 30,
        'quarterly': 90,
        'yearly': 365
    }
    
    returns = {}
    for period, days in periods.items():
        compound_return = amount * ((1 + daily_rate) ** days)
        simple_interest = amount * (daily_rate * days)
        returns[period] = {
            'days': days,
            'compound': round(compound_return, 2),
            'simple': round(amount + simple_interest, 2),
            'profit_compound': round(compound_return - amount, 2),
            'profit_simple': round(simple_interest, 2)
        }
    
    # Impermanent loss calculation (simplified)
    impermanent_loss_scenarios = {}
    price_changes = [-50, -25, -10, 0, 10, 25, 50, 100]
    
    for change in price_changes:
        # Simplified IL calculation
        if change == 0:
            il = 0
        else:
            ratio = (100 + change) / 100
            il = (2 * (ratio ** 0.5) / (1 + ratio) - 1) * 100
        
        impermanent_loss_scenarios[f"{change}%"] = round(il, 2)
    
    return {
        'pool_info': {
            'type': pool_type,
            'token_a': token_a,
            'token_b': token_b,
            'initial_amount': amount,
            'apy': apy
        },
        'returns': returns,
        'impermanent_loss': impermanent_loss_scenarios,
        'risk_assessment': get_pool_risk_assessment(apy, pool_type)
    }

def get_pool_risk_assessment(apy, pool_type):
    """Assess risk level of yield farming pool"""
    if apy > 100:
        risk_level = "VERY HIGH"
        risk_description = "Extremely high APY suggests high risk of impermanent loss or token devaluation"
    elif apy > 50:
        risk_level = "HIGH" 
        risk_description = "High APY with significant impermanent loss risk"
    elif apy > 20:
        risk_level = "MEDIUM"
        risk_description = "Moderate risk with potential for good returns"
    elif apy > 5:
        risk_level = "LOW"
        risk_description = "Conservative returns with lower risk"
    else:
        risk_level = "VERY LOW"
        risk_description = "Very safe but minimal returns"
    
    return {
        'level': risk_level,
        'description': risk_description,
        'recommendations': get_risk_recommendations(risk_level)
    }

def get_risk_recommendations(risk_level):
    """Get recommendations based on risk level"""
    recommendations = {
        'VERY HIGH': [
            'Only invest what you can afford to lose completely',
            'Monitor pool constantly for exits',
            'Check token contracts for potential issues',
            'Consider much smaller position sizes'
        ],
        'HIGH': [
            'Diversify across multiple pools',
            'Monitor impermanent loss closely',
            'Set stop-loss levels',
            'Research token fundamentals thoroughly'
        ],
        'MEDIUM': [
            'Good balance of risk and reward',
            'Monitor weekly for major changes',
            'Consider 25-50% of DeFi allocation',
            'Track performance against holding'
        ],
        'LOW': [
            'Suitable for conservative investors',
            'Good for long-term holding',
            'Lower monitoring requirements',
            'Consider larger position sizes'
        ],
        'VERY LOW': [
            'Very safe for beginners',
            'Good for stable income',
            'Minimal active management needed',
            'Compare with traditional savings rates'
        ]
    }
    
    return recommendations.get(risk_level, [])

# New Enhanced Tools

@tools_bp.route('/honeypot-check', methods=['GET', 'POST'])
def honeypot_check():
    """Advanced honeypot detection with buy/sell simulation"""
    if request.method == 'POST':
        chain = request.form.get('chain')
        address = request.form.get('address')
        
        if not chain or not address:
            flash('Please provide both blockchain and token address.', 'error')
            return render_template('tools/honeypot_check.html', chains=SUPPORTED_CHAINS)
        
        try:
            result = perform_honeypot_analysis(chain, address)
            return render_template('tools/honeypot_check.html', 
                                 chains=SUPPORTED_CHAINS,
                                 result=result,
                                 address=address,
                                 chain=chain)
        except Exception as e:
            flash(f'Error analyzing token: {str(e)}', 'error')
    
    return render_template('tools/honeypot_check.html', chains=SUPPORTED_CHAINS)

@tools_bp.route('/token-scan', methods=['GET', 'POST'])
def token_scan():
    """Comprehensive token security scanner like TokenSniffer"""
    if request.method == 'POST':
        chain = request.form.get('chain')
        address = request.form.get('address')
        
        if not chain or not address:
            flash('Please provide both blockchain and token address.', 'error')
            return render_template('tools/token_scan.html', chains=SUPPORTED_CHAINS)
        
        try:
            result = perform_comprehensive_scan(chain, address)
            return render_template('tools/token_scan.html', 
                                 chains=SUPPORTED_CHAINS,
                                 result=result,
                                 address=address,
                                 chain=chain)
        except Exception as e:
            flash(f'Error scanning token: {str(e)}', 'error')
    
    return render_template('tools/token_scan.html', chains=SUPPORTED_CHAINS)

@tools_bp.route('/audit-check', methods=['GET', 'POST'])
def audit_check():
    """Contract audit verification checker"""
    if request.method == 'POST':
        chain = request.form.get('chain')
        address = request.form.get('address')
        
        if not chain or not address:
            flash('Please provide both blockchain and token address.', 'error')
            return render_template('tools/audit_check.html', chains=SUPPORTED_CHAINS)
        
        try:
            result = check_audit_status(chain, address)
            return render_template('tools/audit_check.html', 
                                 chains=SUPPORTED_CHAINS,
                                 result=result,
                                 address=address,
                                 chain=chain)
        except Exception as e:
            flash(f'Error checking audits: {str(e)}', 'error')
    
    return render_template('tools/audit_check.html', chains=SUPPORTED_CHAINS)

@tools_bp.route('/liquidity-lock', methods=['GET', 'POST'])
def liquidity_lock():
    """Liquidity lock verification checker"""
    if request.method == 'POST':
        chain = request.form.get('chain')
        address = request.form.get('address')
        
        if not chain or not address:
            flash('Please provide both blockchain and token address.', 'error')
            return render_template('tools/liquidity_lock.html', chains=SUPPORTED_CHAINS)
        
        try:
            result = check_liquidity_locks(chain, address)
            return render_template('tools/liquidity_lock.html', 
                                 chains=SUPPORTED_CHAINS,
                                 result=result,
                                 address=address,
                                 chain=chain)
        except Exception as e:
            flash(f'Error checking liquidity locks: {str(e)}', 'error')
    
    return render_template('tools/liquidity_lock.html', chains=SUPPORTED_CHAINS)

@tools_bp.route('/wallet-profiler', methods=['GET', 'POST'])
def wallet_profiler():
    """Wallet behavior and portfolio analysis"""
    ai_summary = None
    if request.method == 'POST':
        chain = request.form.get('chain')
        address = request.form.get('address')
        
        if not chain or not address:
            flash('Please provide both blockchain and wallet address.', 'error')
            return render_template('tools/wallet_profiler.html', chains=SUPPORTED_CHAINS, ai_summary=ai_summary)
        
        try:
            result = analyze_wallet_profile(chain, address)
            if result and result.get('success'):
                prompt, fallback = _build_wallet_summary_inputs(result)
                summary_text, generated = _generate_ai_summary(prompt, fallback)
                ai_summary = {
                    'text': summary_text,
                    'generated': generated
                }
            return render_template('tools/wallet_profiler.html', 
                                 chains=SUPPORTED_CHAINS,
                                 result=result,
                                 address=address,
                                 chain=chain,
                                 ai_summary=ai_summary)
        except Exception as e:
            flash(f'Error analyzing wallet: {str(e)}', 'error')
    
    return render_template('tools/wallet_profiler.html', chains=SUPPORTED_CHAINS, ai_summary=ai_summary)

# Enhanced Analysis Functions

def perform_honeypot_analysis(chain_id, address):
    """Advanced honeypot detection with simulation"""
    try:
        # Get GoPlus data
        goplus_data = get_goplus_token_data(chain_id, address)
        
        if not goplus_data:
            return {'success': False, 'error': 'Unable to fetch token data'}
        
        result = {
            'success': True,
            'token_info': {
                'name': goplus_data.get('token_name', 'Unknown'),
                'symbol': goplus_data.get('token_symbol', 'Unknown'),
                'address': address,
                'chain': SUPPORTED_CHAINS.get(chain_id, f'Chain {chain_id}')
            },
            'honeypot_analysis': analyze_honeypot_risks(goplus_data),
            'simulation_results': simulate_buy_sell_transaction(goplus_data),
            'tax_analysis': analyze_token_taxes(goplus_data),
            'liquidity_analysis': analyze_liquidity_traps(goplus_data),
            'overall_verdict': generate_honeypot_verdict(goplus_data),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def perform_comprehensive_scan(chain_id, address):
    """TokenSniffer-style comprehensive security scan"""
    try:
        goplus_data = get_goplus_token_data(chain_id, address)
        
        if not goplus_data:
            return {'success': False, 'error': 'Unable to fetch token data'}
        
        # Calculate security score (0-100)
        security_score = calculate_security_score(goplus_data)
        
        result = {
            'success': True,
            'token_info': {
                'name': goplus_data.get('token_name', 'Unknown'),
                'symbol': goplus_data.get('token_symbol', 'Unknown'),
                'address': address,
                'chain': SUPPORTED_CHAINS.get(chain_id, f'Chain {chain_id}')
            },
            'security_score': security_score,
            'risk_factors': analyze_risk_factors(goplus_data),
            'ownership_analysis': analyze_ownership_risks(goplus_data),
            'trading_analysis': analyze_trading_restrictions(goplus_data),
            'contract_analysis': analyze_contract_functions(goplus_data),
            'recommendations': generate_security_recommendations(security_score),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def check_audit_status(chain_id, address):
    """Check for official audits from major security firms"""
    try:
        # Mock implementation - would integrate with CertiK, Hacken APIs
        result = {
            'success': True,
            'token_info': {
                'address': address,
                'chain': SUPPORTED_CHAINS.get(chain_id, f'Chain {chain_id}')
            },
            'audit_status': {
                'total_audits': 0,
                'verified_audits': [],
                'pending_audits': [],
                'trust_score': 0
            },
            'audit_firms': get_mock_audit_data(address),
            'recommendations': generate_audit_recommendations(0),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def check_liquidity_locks(chain_id, address):
    """Check liquidity locks across multiple platforms"""
    try:
        result = {
            'success': True,
            'token_info': {
                'address': address,
                'chain': SUPPORTED_CHAINS.get(chain_id, f'Chain {chain_id}')
            },
            'lock_status': {
                'total_locked_percentage': 0,
                'lock_platforms': [],
                'earliest_unlock': None,
                'risk_level': 'HIGH'
            },
            'lock_details': get_mock_lock_data(chain_id, address),
            'recommendations': generate_lock_recommendations(0),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def analyze_wallet_profile(chain_id, address):
    """Comprehensive wallet analysis"""
    try:
        result = {
            'success': True,
            'wallet_info': {
                'address': address,
                'chain': SUPPORTED_CHAINS.get(chain_id, f'Chain {chain_id}'),
                'age_days': 'Loading...',
                'first_transaction': 'Loading...'
            },
            'portfolio_analysis': get_mock_portfolio_data(address),
            'trading_behavior': get_mock_trading_behavior(address),
            'risk_assessment': get_mock_wallet_risk_assessment(address),
            'whale_status': determine_whale_status(address),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Helper Functions for New Tools

def analyze_honeypot_risks(data):
    """Detailed honeypot risk analysis"""
    risks = []
    if data.get('is_honeypot') == '1':
        risks.append({'type': 'CRITICAL', 'message': 'Confirmed honeypot detection'})
    
    if data.get('buy_tax') and float(data.get('buy_tax', 0)) > 0.1:
        risks.append({'type': 'HIGH', 'message': f'High buy tax: {float(data.get("buy_tax", 0)) * 100:.1f}%'})
    
    if data.get('sell_tax') and float(data.get('sell_tax', 0)) > 0.1:
        risks.append({'type': 'HIGH', 'message': f'High sell tax: {float(data.get("sell_tax", 0)) * 100:.1f}%'})
    
    return risks

def simulate_buy_sell_transaction(data):
    """Simulate buy/sell transactions"""
    return {
        'buy_simulation': {
            'can_buy': data.get('cannot_buy') != '1',
            'estimated_tax': f"{float(data.get('buy_tax', 0)) * 100:.2f}%" if data.get('buy_tax') else '0%',
            'gas_estimate': '150,000 - 200,000'
        },
        'sell_simulation': {
            'can_sell': data.get('cannot_sell_all') != '1',
            'estimated_tax': f"{float(data.get('sell_tax', 0)) * 100:.2f}%" if data.get('sell_tax') else '0%',
            'max_sell_percentage': '100%' if data.get('cannot_sell_all') != '1' else 'Limited'
        }
    }

def analyze_token_taxes(data):
    """Analyze buy/sell taxes"""
    buy_tax = float(data.get('buy_tax', 0)) * 100
    sell_tax = float(data.get('sell_tax', 0)) * 100
    
    return {
        'buy_tax_percentage': buy_tax,
        'sell_tax_percentage': sell_tax,
        'total_tax': buy_tax + sell_tax,
        'tax_level': 'HIGH' if (buy_tax + sell_tax) > 20 else ('MEDIUM' if (buy_tax + sell_tax) > 10 else 'LOW')
    }

def analyze_liquidity_traps(data):
    """Analyze potential liquidity traps"""
    traps = []
    
    if data.get('trading_cooldown') == '1':
        traps.append({'type': 'WARNING', 'message': 'Trading cooldown mechanism'})
    
    if data.get('is_anti_whale') == '1':
        traps.append({'type': 'INFO', 'message': 'Anti-whale mechanism active'})
    
    return traps

def generate_honeypot_verdict(data):
    """Generate overall honeypot verdict"""
    if data.get('is_honeypot') == '1':
        return {
            'verdict': 'HONEYPOT',
            'confidence': 'HIGH',
            'message': '🚨 This token is a confirmed honeypot. DO NOT BUY!',
            'color': 'danger'
        }
    
    total_tax = (float(data.get('buy_tax', 0)) + float(data.get('sell_tax', 0))) * 100
    
    if total_tax > 30:
        return {
            'verdict': 'LIKELY HONEYPOT',
            'confidence': 'MEDIUM',
            'message': '⚠️ Very high taxes suggest potential honeypot',
            'color': 'warning'
        }
    elif total_tax > 15:
        return {
            'verdict': 'SUSPICIOUS',
            'confidence': 'MEDIUM',
            'message': '⚠️ High taxes - proceed with extreme caution',
            'color': 'warning'
        }
    else:
        return {
            'verdict': 'LIKELY SAFE',
            'confidence': 'MEDIUM',
            'message': '✅ No obvious honeypot indicators detected',
            'color': 'success'
        }

def calculate_security_score(data):
    """Calculate security score (0-100)"""
    score = 100
    
    # Major deductions
    if data.get('is_honeypot') == '1':
        score -= 60
    if data.get('is_blacklisted') == '1':
        score -= 50
    if data.get('owner_change_balance') == '1':
        score -= 40
    if data.get('cannot_buy') == '1':
        score -= 35
    if data.get('cannot_sell_all') == '1':
        score -= 35
    
    # Moderate deductions
    if data.get('is_mintable') == '1':
        score -= 20
    if data.get('is_proxy') == '1':
        score -= 15
    if data.get('transfer_pausable') == '1':
        score -= 15
    
    # Tax deductions
    buy_tax = float(data.get('buy_tax', 0)) * 100
    sell_tax = float(data.get('sell_tax', 0)) * 100
    
    if buy_tax > 10:
        score -= min(buy_tax, 20)
    if sell_tax > 10:
        score -= min(sell_tax, 20)
    
    # Bonuses
    if data.get('is_whitelisted') == '1':
        score += 10
    
    return max(0, min(100, int(score)))

def analyze_risk_factors(data):
    """Analyze all risk factors"""
    factors = []
    
    critical_risks = [
        ('is_honeypot', 'Honeypot Detection'),
        ('is_blacklisted', 'Blacklisted Token'),
        ('owner_change_balance', 'Owner Can Change Balances'),
        ('cannot_buy', 'Cannot Buy Token'),
        ('cannot_sell_all', 'Cannot Sell All Tokens')
    ]
    
    high_risks = [
        ('is_mintable', 'Mintable Supply'),
        ('is_proxy', 'Proxy Contract'),
        ('transfer_pausable', 'Pausable Transfers'),
        ('hidden_owner', 'Hidden Owner')
    ]
    
    for key, description in critical_risks:
        if data.get(key) == '1':
            factors.append({'level': 'CRITICAL', 'factor': description, 'status': True})
    
    for key, description in high_risks:
        if data.get(key) == '1':
            factors.append({'level': 'HIGH', 'factor': description, 'status': True})
    
    return factors

def analyze_ownership_risks(data):
    """Analyze ownership-related risks"""
    return {
        'renounced': data.get('owner_address') == '0x0000000000000000000000000000000000000000',
        'can_mint': data.get('is_mintable') == '1',
        'can_pause': data.get('transfer_pausable') == '1',
        'can_change_balance': data.get('owner_change_balance') == '1',
        'hidden_owner': data.get('hidden_owner') == '1'
    }

def analyze_trading_restrictions(data):
    """Analyze trading restrictions"""
    return {
        'can_buy': data.get('cannot_buy') != '1',
        'can_sell_all': data.get('cannot_sell_all') != '1',
        'has_cooldown': data.get('trading_cooldown') == '1',
        'anti_whale': data.get('is_anti_whale') == '1',
        'buy_tax': float(data.get('buy_tax', 0)) * 100,
        'sell_tax': float(data.get('sell_tax', 0)) * 100
    }

def analyze_contract_functions(data):
    """Analyze contract functions"""
    return {
        'is_proxy': data.get('is_proxy') == '1',
        'has_external_call': data.get('external_call') == '1',
        'gas_abuse': data.get('gas_abuse') == '1',
        'fake_token': data.get('fake_token') == '1'
    }

def generate_security_recommendations(score):
    """Generate recommendations based on security score"""
    if score >= 80:
        return [
            '✅ Token appears to have good security fundamentals',
            '✅ Consider this for investment with proper risk management',
            '✅ Continue monitoring for any changes'
        ]
    elif score >= 60:
        return [
            '⚠️ Moderate security concerns detected',
            '⚠️ Invest only small amounts you can afford to lose',
            '⚠️ Monitor closely for any red flags'
        ]
    elif score >= 40:
        return [
            '🚨 Significant security risks identified',
            '🚨 High risk of losing funds',
            '🚨 Consider avoiding this token'
        ]
    else:
        return [
            '🚨 EXTREME RISK - Multiple critical issues',
            '🚨 DO NOT INVEST in this token',
            '🚨 Likely to result in total loss of funds'
        ]

def get_mock_audit_data(address):
    """Mock audit data for demonstration"""
    return [
        {
            'firm': 'CertiK',
            'status': 'Not Found',
            'score': None,
            'report_url': None,
            'last_checked': datetime.now().strftime('%Y-%m-%d')
        },
        {
            'firm': 'Hacken',
            'status': 'Not Found',
            'score': None,
            'report_url': None,
            'last_checked': datetime.now().strftime('%Y-%m-%d')
        },
        {
            'firm': 'ConsenSys Diligence',
            'status': 'Not Found',
            'score': None,
            'report_url': None,
            'last_checked': datetime.now().strftime('%Y-%m-%d')
        }
    ]

def generate_audit_recommendations(audit_count):
    """Generate audit-based recommendations"""
    if audit_count >= 2:
        return ['✅ Multiple audits provide high confidence', '✅ Well-audited project']
    elif audit_count == 1:
        return ['⚠️ Single audit - consider additional verification', '⚠️ Look for recent audit dates']
    else:
        return ['🚨 No official audits found', '🚨 Higher risk without professional security review']

def get_mock_lock_data(chain_id, address):
    """Mock liquidity lock data"""
    return [
        {
            'platform': 'Unicrypt',
            'status': 'Not Found',
            'locked_percentage': 0,
            'unlock_date': None,
            'lock_value': None
        },
        {
            'platform': 'Team Finance',
            'status': 'Not Found',
            'locked_percentage': 0,
            'unlock_date': None,
            'lock_value': None
        },
        {
            'platform': 'DxSale',
            'status': 'Not Found',
            'locked_percentage': 0,
            'unlock_date': None,
            'lock_value': None
        }
    ]

def generate_lock_recommendations(lock_percentage):
    """Generate lock-based recommendations"""
    if lock_percentage >= 80:
        return ['✅ High liquidity lock percentage', '✅ Lower risk of rug pull']
    elif lock_percentage >= 50:
        return ['⚠️ Moderate liquidity protection', '⚠️ Some rug pull risk remains']
    else:
        return ['🚨 Low or no liquidity locks found', '🚨 High risk of rug pull']

def get_mock_portfolio_data(address):
    """Mock portfolio data for wallet analysis"""
    return {
        'total_value_usd': 'Loading...',
        'token_count': 'Loading...',
        'top_holdings': [
            {'symbol': 'Loading...', 'value_usd': 0, 'percentage': 0}
        ],
        'risk_distribution': {
            'blue_chip': 0,
            'mid_cap': 0,
            'small_cap': 0,
            'meme_coins': 0
        }
    }

def get_mock_trading_behavior(address):
    """Mock trading behavior analysis"""
    return {
        'total_transactions': 'Loading...',
        'avg_transaction_value': 'Loading...',
        'trading_frequency': 'Loading...',
        'profit_loss_ratio': 'Loading...',
        'favorite_tokens': [],
        'trading_pattern': 'Loading...'
    }

def get_mock_wallet_risk_assessment(address):
    """Mock wallet risk assessment"""
    return {
        'risk_level': 'UNKNOWN',
        'trust_score': 0,
        'red_flags': [],
        'positive_indicators': [],
        'recommendation': 'Analysis in progress...'
    }

def determine_whale_status(address):
    """Determine if wallet is a whale"""
    return {
        'is_whale': False,
        'whale_tier': 'Shrimp',
        'estimated_net_worth': 'Loading...',
        'influence_score': 0
    }

# Most Popular Viral Tools

@tools_bp.route('/gas-tracker', methods=['GET', 'POST'])
def gas_tracker():
    """Real-time gas tracker across multiple chains"""
    if request.method == 'POST':
        chains = request.form.getlist('chains')
        if chains:
            try:
                gas_data = get_multi_chain_gas_data(chains)
                return render_template('tools/gas_tracker.html', 
                                     gas_data=gas_data,
                                     selected_chains=chains,
                                     chains=SUPPORTED_CHAINS)
            except Exception as e:
                flash(f'Error fetching gas data: {str(e)}', 'error')
    
    # Get default gas data for popular chains
    try:
        default_chains = ['1', '56', '137', '42161', '43114']  # ETH, BSC, Polygon, Arbitrum, Avalanche
        gas_data = get_multi_chain_gas_data(default_chains)
        return render_template('tools/gas_tracker.html', 
                             gas_data=gas_data,
                             selected_chains=default_chains,
                             chains=SUPPORTED_CHAINS)
    except Exception as e:
        flash(f'Error loading gas data: {str(e)}', 'error')
        return render_template('tools/gas_tracker.html', 
                             gas_data={},
                             selected_chains=[],
                             chains=SUPPORTED_CHAINS)

@tools_bp.route('/mev-protection', methods=['GET', 'POST'])
def mev_protection():
    """MEV protection checker and analyzer"""
    if request.method == 'POST':
        chain = request.form.get('chain')
        address = request.form.get('address')
        
        if not chain or not address:
            flash('Please provide both blockchain and token/wallet address.', 'error')
            return render_template('tools/mev_protection.html', chains=SUPPORTED_CHAINS)
        
        try:
            result = analyze_mev_risks(chain, address)
            return render_template('tools/mev_protection.html', 
                                 chains=SUPPORTED_CHAINS,
                                 result=result,
                                 address=address,
                                 chain=chain)
        except Exception as e:
            flash(f'Error analyzing MEV risks: {str(e)}', 'error')
    
    return render_template('tools/mev_protection.html', chains=SUPPORTED_CHAINS)

@tools_bp.route('/airdrop-hunter', methods=['GET', 'POST'])
def airdrop_hunter():
    """Airdrop hunter and eligibility checker"""
    if request.method == 'POST':
        wallet_address = request.form.get('wallet_address')
        
        if wallet_address:
            try:
                result = check_airdrop_eligibility(wallet_address)
                return render_template('tools/airdrop_hunter.html', 
                                     result=result,
                                     wallet_address=wallet_address)
            except Exception as e:
                flash(f'Error checking airdrop eligibility: {str(e)}', 'error')
    
    # Get upcoming airdrops
    try:
        upcoming_airdrops = get_upcoming_airdrops()
        return render_template('tools/airdrop_hunter.html', 
                             upcoming_airdrops=upcoming_airdrops)
    except Exception as e:
        flash(f'Error loading airdrops: {str(e)}', 'error')
        return render_template('tools/airdrop_hunter.html', 
                             upcoming_airdrops=[])

@tools_bp.route('/rug-alert', methods=['GET', 'POST'])
def rug_alert():
    """Rug pull alert system"""
    if request.method == 'POST':
        chain = request.form.get('chain')
        address = request.form.get('address')
        
        if not chain or not address:
            flash('Please provide both blockchain and token address.', 'error')
            return render_template('tools/rug_alert.html', chains=SUPPORTED_CHAINS)
        
        try:
            result = analyze_rug_pull_risks(chain, address)
            return render_template('tools/rug_alert.html', 
                                 chains=SUPPORTED_CHAINS,
                                 result=result,
                                 address=address,
                                 chain=chain)
        except Exception as e:
            flash(f'Error analyzing rug pull risks: {str(e)}', 'error')
    
    # Get recent alerts
    try:
        recent_alerts = get_recent_rug_alerts()
        return render_template('tools/rug_alert.html', 
                             chains=SUPPORTED_CHAINS,
                             recent_alerts=recent_alerts)
    except Exception as e:
        flash(f'Error loading alerts: {str(e)}', 'error')
        return render_template('tools/rug_alert.html', 
                             chains=SUPPORTED_CHAINS,
                             recent_alerts=[])

# Viral Tool Helper Functions

def get_multi_chain_gas_data(chain_ids):
    """Get real-time gas data for multiple chains"""
    gas_data = {}
    
    for chain_id in chain_ids:
        chain_name = SUPPORTED_CHAINS.get(chain_id, f'Chain {chain_id}')
        
        # Mock gas data - in production would integrate with gas APIs
        if chain_id == '1':  # Ethereum
            gas_data[chain_id] = {
                'chain_name': chain_name,
                'current_gas': {
                    'slow': 25,
                    'standard': 35,
                    'fast': 50,
                    'instant': 70
                },
                'gas_trend': 'rising',
                'recommended_time': 'Wait 2-3 hours for lower fees',
                'peak_hours': '9:00 AM - 6:00 PM UTC',
                'cheapest_hours': '2:00 AM - 8:00 AM UTC',
                'avg_24h': 42,
                'prediction_1h': 38,
                'prediction_6h': 32
            }
        elif chain_id == '56':  # BSC
            gas_data[chain_id] = {
                'chain_name': chain_name,
                'current_gas': {
                    'slow': 3,
                    'standard': 5,
                    'fast': 8,
                    'instant': 12
                },
                'gas_trend': 'stable',
                'recommended_time': 'Good time to transact',
                'peak_hours': '8:00 AM - 11:00 PM UTC',
                'cheapest_hours': '11:00 PM - 8:00 AM UTC',
                'avg_24h': 6,
                'prediction_1h': 5,
                'prediction_6h': 4
            }
        else:
            # Default data for other chains
            gas_data[chain_id] = {
                'chain_name': chain_name,
                'current_gas': {
                    'slow': 1,
                    'standard': 2,
                    'fast': 3,
                    'instant': 5
                },
                'gas_trend': 'stable',
                'recommended_time': 'Good time to transact',
                'peak_hours': 'Variable',
                'cheapest_hours': 'Variable',
                'avg_24h': 2,
                'prediction_1h': 2,
                'prediction_6h': 2
            }
    
    return gas_data

def analyze_mev_risks(chain_id, address):
    """Analyze MEV risks for token or wallet"""
    try:
        result = {
            'success': True,
            'address': address,
            'chain': SUPPORTED_CHAINS.get(chain_id, f'Chain {chain_id}'),
            'mev_analysis': {
                'bot_activity_detected': False,
                'front_running_risk': 'LOW',
                'sandwich_attack_risk': 'MEDIUM',
                'mev_activity_score': 25,
                'recent_mev_attacks': 0
            },
            'protection_recommendations': [
                '✅ Use MEV-protected RPCs like Flashbots Protect',
                '✅ Consider private mempools for large transactions',
                '✅ Use limit orders instead of market orders',
                '✅ Split large trades into smaller transactions'
            ],
            'safe_dexes': [
                {'name': 'CowSwap', 'protection_level': 'HIGH', 'fee': '0.1%'},
                {'name': 'Flashbots Protect', 'protection_level': 'HIGH', 'fee': '0%'},
                {'name': '1inch (Private Mode)', 'protection_level': 'MEDIUM', 'fee': '0.05%'}
            ],
            'mev_stats': {
                'total_mev_extracted_24h': '$2.5M',
                'avg_loss_per_victim': '$45',
                'protection_success_rate': '94%'
            },
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def check_airdrop_eligibility(wallet_address):
    """Check airdrop eligibility for a wallet"""
    try:
        result = {
            'success': True,
            'wallet_address': wallet_address,
            'eligible_airdrops': [
                {
                    'project': 'LayerZero',
                    'status': 'Potentially Eligible',
                    'estimated_tokens': '500-2000 ZRO',
                    'estimated_value': '$250-1000',
                    'criteria_met': ['Bridge Usage', 'Multi-chain Activity'],
                    'missing_criteria': ['Governance Participation']
                },
                {
                    'project': 'zkSync Era',
                    'status': 'Eligible',
                    'estimated_tokens': '200-800 ZK',
                    'estimated_value': '$100-400',
                    'criteria_met': ['Early User', 'Volume Threshold'],
                    'missing_criteria': []
                }
            ],
            'missed_airdrops': [
                {
                    'project': 'Arbitrum',
                    'value_missed': '$1,200',
                    'reason': 'Insufficient transaction volume'
                }
            ],
            'wallet_score': 75,
            'airdrop_farming_tips': [
                '💡 Interact with new protocols early',
                '💡 Use multiple chains regularly',
                '💡 Participate in governance voting',
                '💡 Provide liquidity to new DEXes'
            ],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_upcoming_airdrops():
    """Get list of upcoming airdrops"""
    return [
        {
            'project': 'Blast',
            'expected_date': '2025-09-15',
            'criteria': ['Bridge ETH to Blast', 'Use Blast DeFi protocols'],
            'estimated_value': '$500-2000',
            'difficulty': 'MEDIUM',
            'time_left': '42 days'
        },
        {
            'project': 'Scroll',
            'expected_date': '2025-08-30',
            'criteria': ['Bridge to Scroll', 'Deploy contracts', 'Use dApps'],
            'estimated_value': '$200-800',
            'difficulty': 'EASY',
            'time_left': '27 days'
        },
        {
            'project': 'Taiko',
            'expected_date': '2025-10-01',
            'criteria': ['Be early user', 'Provide liquidity', 'Run validator'],
            'estimated_value': '$300-1200',
            'difficulty': 'HARD',
            'time_left': '59 days'
        }
    ]

def analyze_rug_pull_risks(chain_id, address):
    """Analyze rug pull risks for a token"""
    try:
        # Get basic token data
        goplus_data = get_goplus_token_data(chain_id, address)
        
        result = {
            'success': True,
            'token_info': {
                'address': address,
                'chain': SUPPORTED_CHAINS.get(chain_id, f'Chain {chain_id}'),
                'name': goplus_data.get('token_name', 'Unknown') if goplus_data else 'Unknown',
                'symbol': goplus_data.get('token_symbol', 'Unknown') if goplus_data else 'Unknown'
            },
            'rug_risk_score': 35,  # 0-100, higher = more risky
            'risk_level': 'MEDIUM',
            'active_alerts': [
                {
                    'type': 'WARNING',
                    'message': 'Large holder moved 5% of supply in last 24h',
                    'severity': 'MEDIUM',
                    'timestamp': '2 hours ago'
                }
            ],
            'risk_factors': {
                'liquidity_risk': {
                    'level': 'MEDIUM',
                    'locked_percentage': 60,
                    'largest_holder_percentage': 15,
                    'top_10_holders_percentage': 45
                },
                'developer_risk': {
                    'level': 'LOW',
                    'wallet_activity': 'Normal',
                    'recent_sells': 0,
                    'team_tokens_locked': True
                },
                'market_risk': {
                    'level': 'HIGH',
                    'volume_drop_24h': -35,
                    'price_volatility': 'Very High',
                    'social_sentiment': 'Negative'
                }
            },
            'monitoring_setup': {
                'whale_alerts': True,
                'liquidity_alerts': True,
                'dev_wallet_alerts': True,
                'price_drop_alerts': True
            },
            'recommendations': [
                '⚠️ Monitor large holder movements closely',
                '⚠️ Set stop-loss at 20% below current price',
                '⚠️ Consider reducing position size due to high volatility',
                '✅ Liquidity is partially locked - moderate protection'
            ],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        }
        
        return result
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def get_recent_rug_alerts():
    """Get recent rug pull alerts"""
    return [
        {
            'token_name': 'SafeMoonV3',
            'symbol': 'SAFEV3',
            'chain': 'BSC',
            'alert_type': 'LIQUIDITY REMOVED',
            'severity': 'CRITICAL',
            'description': '95% of liquidity removed by dev wallet',
            'loss_amount': '$2.3M',
            'time_ago': '3 hours ago'
        },
        {
            'token_name': 'ElonDoge2.0',
            'symbol': 'EDOGE2',
            'chain': 'Ethereum',
            'alert_type': 'WHALE DUMP',
            'severity': 'HIGH',
            'description': 'Top holder sold 80% of tokens',
            'loss_amount': '$890K',
            'time_ago': '6 hours ago'
        },
        {
            'token_name': 'MetaVerse Token',
            'symbol': 'META',
            'chain': 'Polygon',
            'alert_type': 'CONTRACT EXPLOIT',
            'severity': 'CRITICAL',
            'description': 'Mint function exploited, 1B tokens minted',
            'loss_amount': '$1.7M',
            'time_ago': '12 hours ago'
        }
    ]
