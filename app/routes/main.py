from flask import Blueprint, render_template, request, redirect, url_for, flash, make_response, session, jsonify
from app.models.payment_session import PaymentSession
from ..utils.timezone import now_eest
from app.extensions import db
from datetime import datetime, timedelta
from flask_login import current_user

main_bp = Blueprint('main', __name__)

@main_bp.route('/', methods=['GET'])
def home():
    # Optional: Redirect authenticated users to their dashboards
    if current_user.is_authenticated:
        if hasattr(current_user, 'is_admin') and callable(current_user.is_admin) and current_user.is_admin():
            return redirect(url_for("admin.admin_dashboard"))
        else:
            return redirect(url_for("client.client_dashboard"))
    return render_template('index.html')

# Public payment form route
@main_bp.route('/pay', methods=['GET', 'POST'])
def pay():
    if request.method == 'POST':
        amount = request.form.get('amount')
        coin = request.form.get('coin')
        email = request.form.get('email')
        client_id = 1
        order_id = f'ORD_{int(now_eest().timestamp())}'
        expires = now_eest() + timedelta(minutes=30)
        # Store coin in currency field for PaymentSession
        ps = PaymentSession(
            public_id='ps_' + __import__('uuid').uuid4().hex[:12],
            client_id=client_id,
            order_id=order_id,
            amount=amount,
            currency=coin,
            customer_email=email,
            status='created',
            expires_at=expires,
            success_url=url_for('main.home', _external=True),
            cancel_url=url_for('main.home', _external=True)
        )
        db.session.add(ps)
        db.session.commit()
        return redirect(url_for('checkout.checkout', ps_id=ps.public_id))
    return render_template('pay.html')


# --- Root-level Health Check Endpoint ---
@main_bp.route('/health', methods=['GET'])
def health():
    return make_response({'status': 'ok', 'message': 'Service healthy'}, 200)

@main_bp.route('/set_language', methods=['GET'])
def set_language():
    lang = request.args.get('language')
    if lang in ['en', 'tr']:
        session['lang'] = lang
    return redirect(request.referrer or url_for('main.home'))




# Public payment page for viewing payment details by ID
@main_bp.route('/payment/<int:payment_id>', methods=['GET'])
def payment_page(payment_id: int):
    try:
        from app.models import Payment
        payment = Payment.query.get(payment_id)
    except Exception:
        payment = None
    if not payment:
        # Render a simple 404-ish page to avoid exposing stack traces
        return render_template('error/400.html', title='Payment Not Found'), 404
    return render_template('payment/view.html', payment=payment)

@main_bp.route('/pricing')
def pricing():
    return render_template('pricing.html')

@main_bp.route('/blog')
def blog_index():
    """Blog index for Engine B articles and guides."""
    return render_template('blog_index.html')

@main_bp.route('/blog/usdt-deposits-for-betting-platforms')
def blog_usdt_deposits_for_betting_platforms():
    """Engine B article: USDT deposits for betting platforms."""
    return render_template('blog_usdt_deposits_betting.html')

# Engine A - Anchor Pages (SEO Money Pages)
@main_bp.route('/betting-crypto-gateway')
def betting_crypto_gateway():
    """Primary SEO landing page for betting platforms"""
    return render_template('betting_crypto_gateway.html')

@main_bp.route('/usdt-deposit-api')
def usdt_deposit_api():
    """Technical page for developers looking for USDT deposit API"""
    return render_template('usdt_deposit_api.html')

@main_bp.route('/usdt-deposit-api/python')
def usdt_deposit_api_python():
    """Python integration guide for USDT deposit API"""
    return render_template('usdt_deposit_api_python.html')

@main_bp.route('/usdt-deposit-api/php')
def usdt_deposit_api_php():
    """PHP integration guide for USDT deposit API"""
    return render_template('usdt_deposit_api_php.html')

@main_bp.route('/usdt-deposit-api/nodejs')
def usdt_deposit_api_nodejs():
    """Node.js integration guide for USDT deposit API"""
    return render_template('usdt_deposit_api_nodejs.html')

@main_bp.route('/crypto-gateway-for-casinos')
def crypto_gateway_for_casinos():
    """Global casino market landing page"""
    return render_template('crypto_gateway_for_casinos.html')


@main_bp.route('/paycrypt-vs-coinspaid')
def paycrypt_vs_coinspaid():
    """Comparison page: PayCrypt vs CoinsPaid"""
    return render_template('paycrypt_vs_coinspaid.html')


@main_bp.route('/paycrypt-vs-danapay')
def paycrypt_vs_danapay():
    """Comparison page: PayCrypt vs Danapay"""
    return render_template('paycrypt_vs_danapay.html')

# --- API Blueprint and Heartbeat Endpoint (stub) ---
api_bp = Blueprint('api', __name__, url_prefix='/api')

@api_bp.route('/status/heartbeat')
def status_heartbeat():
    return jsonify({'status': 'ok', 'message': 'API is alive'})

# In your app factory or main __init__, ensure to register api_bp
# app.register_blueprint(api_bp)
