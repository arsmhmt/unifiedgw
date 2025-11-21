from flask import Blueprint, render_template, redirect, request, url_for, flash, jsonify, g
from flask_login import login_required, current_user
from decimal import Decimal
from types import SimpleNamespace
from app.models import User, Client, Payment, WithdrawalRequest, RecurringPayment
from app.models.bank_gateway import (
    BankGatewayProvider,
    BankGatewayAccount,
    BankGatewayClientSite,
    BankGatewayAPIKey,
    BankGatewayTransaction,
    BankGatewayDepositRequest,
    BankGatewayWithdrawalRequest,
    BankGatewayProviderCommission
)
from app.forms import ClientForm, RecurringPaymentForm
from app import db
from app.utils.decorators import superadmin_required
from app.decorators import admin_required
from datetime import datetime, timedelta
from ..utils.timezone import now_eest
import uuid
import secrets
from sqlalchemy.orm import joinedload

from app.models.enums import PaymentStatus, WithdrawalStatus

admin_bp = Blueprint("admin", __name__, url_prefix="/admin120724")

from flask_babel import _


def _format_seconds(seconds):
    """Convert seconds to human-readable duration string."""
    if seconds is None:
        return None
    try:
        seconds = float(seconds)
    except (TypeError, ValueError):
        return None

    if seconds < 60:
        return f"{int(seconds)}s"
    minutes, secs = divmod(int(seconds), 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"
    hours, mins = divmod(minutes, 60)
    return f"{hours}h {mins}m"


@admin_bp.context_processor
def inject_admin_globals():
    """Provide common template helpers for admin views."""
    return {
        'current_time': now_eest(),
    }


# --- Admin Dashboard ---
@admin_bp.route("/dashboard")
@login_required
# @superadmin_required
def admin_dashboard():
    # Debug logging
    print(f"[DEBUG] Admin dashboard - Current user: {current_user}, is_authenticated: {current_user.is_authenticated}")
    print(f"[DEBUG] User attributes: {dir(current_user)}")
    if hasattr(current_user, 'role'):
        print(f"[DEBUG] User role: {getattr(current_user.role, 'name', 'No role')}")
    
    try:
        now = now_eest()
        last_24h = now - timedelta(hours=24)
        last_30d = now - timedelta(days=30)
        prev_30d_start = now - timedelta(days=60)

        def to_decimal(value):
            if value is None:
                return Decimal("0")
            if isinstance(value, Decimal):
                return value
            return Decimal(str(value))

        def to_float(value):
            if value is None:
                return 0.0
            if isinstance(value, Decimal):
                return float(value)
            return float(value)

        clients = Client.query.all()
        total_clients = len(clients)
        active_clients = Client.query.filter_by(is_active=True).count()
        verified_clients = Client.query.filter_by(is_verified=True).count()

        total_payments = Payment.query.count()
        completed_payments = Payment.query.filter(Payment.status == PaymentStatus.COMPLETED).count()
        payments_last_24h = Payment.query.filter(Payment.created_at >= last_24h).all()
        payments_last_30d = Payment.query.filter(Payment.created_at >= last_30d).all()
        payments_prev_30d = Payment.query.filter(Payment.created_at >= prev_30d_start, Payment.created_at < last_30d).all()

        total_fiat_volume = to_decimal(
            db.session.query(db.func.coalesce(db.func.sum(Payment.fiat_amount), 0)).scalar()
        )
        total_crypto_volume = to_decimal(
            db.session.query(db.func.coalesce(db.func.sum(Payment.crypto_amount), 0)).scalar()
        )
        volume_24h = sum(to_decimal(payment.fiat_amount or 0) for payment in payments_last_24h)
        crypto_volume_24h = sum(to_decimal(payment.crypto_amount or 0) for payment in payments_last_24h)

        last_30d_volume = sum(to_decimal(payment.fiat_amount or 0) for payment in payments_last_30d)
        prev_30d_volume = sum(to_decimal(payment.fiat_amount or 0) for payment in payments_prev_30d)

        def growth_rate(current, previous):
            current_value = float(current)
            previous_value = float(previous)
            if previous_value == 0:
                return 100.0 if current_value > 0 else 0.0
            return ((current_value - previous_value) / previous_value) * 100.0

        success_rate = (completed_payments / total_payments * 100) if total_payments else 0.0

        pending_withdrawals = WithdrawalRequest.query.filter(
            WithdrawalRequest.status == WithdrawalStatus.PENDING
        ).count()
        withdrawals_last_24h = WithdrawalRequest.query.filter(
            WithdrawalRequest.created_at >= last_24h
        ).all()
        completed_withdrawals = WithdrawalRequest.query.filter(
            WithdrawalRequest.status == WithdrawalStatus.COMPLETED
        ).all()

        # Bank gateway statistics
        bank_stats = {
            'total_providers': BankGatewayProvider.query.count(),
            'total_accounts': BankGatewayAccount.query.count(),
            'total_bank_clients': BankGatewayClientSite.query.count(),
            'pending_transactions': BankGatewayTransaction.query.filter_by(status='pending').count(),
            'total_transactions_24h': BankGatewayTransaction.query.filter(
                BankGatewayTransaction.created_at >= last_24h
            ).count(),
        }

        last_month = now - timedelta(days=30)
        bank_revenue = db.session.query(
            db.func.coalesce(db.func.sum(BankGatewayTransaction.commission_amount), 0)
        ).filter(
            BankGatewayTransaction.created_at >= last_month,
            BankGatewayTransaction.status == 'confirmed'
        ).scalar() or 0

        recent_bank_transactions = BankGatewayTransaction.query.order_by(
            BankGatewayTransaction.created_at.desc()
        ).limit(5).all()
        current_time = datetime.now()

        sidebar_stats = {
            'total_clients': total_clients,
            'pending_withdrawals': pending_withdrawals,
            'pending_user_withdrawals': pending_withdrawals,
            'pending_client_withdrawals': pending_withdrawals,
            'pending_tickets': 0,
        }

        top_clients = []
        top_clients_query = (
            db.session.query(
                Client,
                db.func.count(Payment.id).label('transaction_count'),
                db.func.coalesce(db.func.sum(Payment.fiat_amount), 0).label('total_fiat_amount'),
                db.func.coalesce(db.func.sum(Payment.crypto_amount), 0).label('total_crypto_amount')
            )
            .join(Payment, Payment.client_id == Client.id)
            .filter(Payment.status == PaymentStatus.COMPLETED)
            .group_by(Client.id)
            .order_by(db.func.coalesce(db.func.sum(Payment.fiat_amount), 0).desc())
            .limit(5)
            .all()
        )
        for client, txn_count, total_fiat, total_crypto in top_clients_query:
            total_volume_value = to_float(to_decimal(total_fiat)) or to_float(to_decimal(total_crypto))
            top_clients.append(
                SimpleNamespace(
                    id=client.id,
                    company_name=client.company_name,
                    email=client.email,
                    transaction_count=txn_count,
                    total_volume=total_volume_value,
                    total_fiat_volume=to_float(to_decimal(total_fiat)),
                    total_crypto_volume=to_float(to_decimal(total_crypto))
                )
            )

        recent_payments = (
            db.session.query(Payment, Client)
            .join(Client, Payment.client_id == Client.id, isouter=True)
            .order_by(Payment.created_at.desc())
            .limit(10)
            .all()
        )

        recent_activity = []
        for payment, client in recent_payments:
            setattr(payment, 'btc_value', to_float(to_decimal(payment.crypto_amount or payment.amount or 0)))
            setattr(payment, 'fiat_display_amount', to_float(to_decimal(payment.fiat_amount or 0)))
            recent_activity.append((payment, client))

        currency_sums = (
            db.session.query(
                Payment.crypto_currency,
                db.func.coalesce(db.func.sum(Payment.crypto_amount), 0).label('total_amount'),
                db.func.count(db.func.distinct(Payment.client_id)).label('client_count')
            )
            .filter(
                Payment.status == PaymentStatus.COMPLETED,
                Payment.crypto_currency.isnot(None)
            )
            .group_by(Payment.crypto_currency)
            .all()
        )

        currency_stats = {}
        for currency, total_amount, client_count in currency_sums:
            key = currency.upper() if currency else 'UNDEFINED'
            currency_stats[key] = {
                'total': to_float(to_decimal(total_amount)),
                'clients': int(client_count),
                'average': to_float(to_decimal(total_amount)) / client_count if client_count else 0.0
            }

        withdrawal_stats = {
            'total': len(completed_withdrawals),
            'pending': pending_withdrawals,
            'last_24h_count': len(withdrawals_last_24h),
            'last_24h_volume': float(sum(w.amount for w in withdrawals_last_24h if w.amount)),
        }

        dashboard_stats = {
            'total_clients': active_clients,
            'total_clients_all': total_clients,
            'verified_clients': verified_clients,
            'pending_withdrawals': pending_withdrawals,
            'total_transactions': total_payments,
            'completed_transactions': completed_payments,
            'total_volume': to_float(total_fiat_volume) if total_fiat_volume else to_float(total_crypto_volume),
            'total_fiat_volume': to_float(total_fiat_volume),
            'total_crypto_volume': to_float(total_crypto_volume),
            'volume_24h': to_float(volume_24h),
            'crypto_volume_24h': to_float(crypto_volume_24h),
            'success_rate': success_rate,
            'revenue_growth': growth_rate(last_30d_volume, prev_30d_volume),
            'transactions_growth': growth_rate(len(payments_last_30d), len(payments_prev_30d)),
            'clients_growth': growth_rate(
                Client.query.filter(Client.created_at >= last_30d).count(),
                Client.query.filter(Client.created_at >= prev_30d_start, Client.created_at < last_30d).count()
            ),
            'commission_growth': 0.0,
            'active_clients_change': 0.0,
            'success_rate_change': 0.0,
            'total_commission': 0.0,
            'commission_change': 0.0,
            'system_load': 12,
            'uptime_days': 99.9,
            'flagged_activities': 0,
            'resolved_tickets': 0,
            'pending_tickets': 0,
            'total_tickets': 0,
            'btc_usd_rate': 45000,
            'eth_usd_rate': 3000,
            'usd_try_rate': 32.5,
            'btc_try_rate': 1500000,
            'total_btc_balance': currency_stats.get('BTC', {}).get('total', 0.0),
            'btc_active_clients': currency_stats.get('BTC', {}).get('clients', 0),
            'avg_btc_balance': currency_stats.get('BTC', {}).get('average', 0.0),
            'total_eth_balance': currency_stats.get('ETH', {}).get('total', 0.0),
            'eth_active_clients': currency_stats.get('ETH', {}).get('clients', 0),
            'avg_eth_balance': currency_stats.get('ETH', {}).get('average', 0.0),
            'total_usdt_balance': currency_stats.get('USDT', {}).get('total', 0.0),
            'usdt_active_clients': currency_stats.get('USDT', {}).get('clients', 0),
            'avg_usdt_balance': currency_stats.get('USDT', {}).get('average', 0.0),
        }

        print(f"[DEBUG] Admin dashboard rendered successfully")
    except Exception as e:
        print(f"[ERROR] Error in admin dashboard: {str(e)}")
        raise
    return render_template("admin/dashboard.html", 
                         clients=clients,
                         stats=dashboard_stats,
                         bank_stats=bank_stats,
                         bank_revenue=bank_revenue,
                         recent_bank_transactions=recent_bank_transactions,
                         current_time=current_time,
                         sidebar_stats=sidebar_stats,
                         top_clients=top_clients,
                         recent_activity=recent_activity,
                         withdrawal_stats=withdrawal_stats)

    # --- Add Client ---
@admin_bp.route("/clients/add", methods=["GET", "POST"])
@login_required
@superadmin_required
def add_client():
    from app.models import ClientPackage, ClientType, User, Role
    packages = ClientPackage.query.filter_by(status='ACTIVE').order_by(ClientPackage.id).all()
    form = ClientForm()
    # Set choices for package_id dropdown
    form.package_id.choices = [(p.id, p.name) for p in packages]
    # Set default to Enterprise Flat Rate if available
    for p in packages:
        if 'enterprise' in p.name.lower():
            form.package_id.default = p.id
            break
    form.process(request.form)
    if form.validate_on_submit():
        try:
            # Ensure client role exists
            client_role = Role.query.filter_by(name='client').first()
            if not client_role:
                # Create client role if it doesn't exist
                client_role = Role(name='client', description='Client user role')
                db.session.add(client_role)
                db.session.flush()  # Ensure role is created before using it
            
            # First create the User record for authentication
            user = User(
                username=form.username.data,
                email=form.email.data,
                role=client_role  # Assign client role directly
            )
            if form.password.data:
                user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.flush()  # Flush to get the user.id
            
            # Then create the Client record linked to the User
            client = Client(
                user_id=user.id,  # Link to the User record
                username=form.username.data,
                email=form.email.data,
                company_name=form.company_name.data,
                name=form.name.data,
                phone=form.phone.data,
                website=form.website.data,
                address=form.address.data,
                city=form.city.data,
                country=form.country.data,
                postal_code=form.postal_code.data,
                tax_id=form.tax_id.data,
                vat_number=form.vat_number.data,
                registration_number=form.registration_number.data,
                contact_person=form.contact_person.data,
                contact_email=form.contact_email.data,
                contact_phone=form.contact_phone.data,
                notes=form.notes.data,
                rate_limit=form.rate_limit.data,
                theme_color=form.theme_color.data,
                deposit_commission_rate=form.deposit_commission_rate.data,
                withdrawal_commission_rate=form.withdrawal_commission_rate.data,
                balance=form.balance.data,
                is_active=form.is_active.data,
                is_verified=form.is_verified.data,
                package_id=form.package_id.data
            )
            if form.password.data:
                client.set_password(form.password.data)  # Also set on client for backup
            
            db.session.add(client)
            db.session.flush()  # Flush to get client.id before generating API key
            
            # Generate API key for the new client
            from app.models import ClientApiKey
            try:
                api_key_obj = ClientApiKey.create_for_admin(
                    client_id=client.id,
                    name=f"{client.company_name} - Production Key",
                    permissions=['deposits', 'withdrawals', 'transactions', 'balance'],
                    rate_limit=client.rate_limit or 100,
                    expires_days=None,  # No expiration for default key
                    created_by_admin_id=current_user.id if hasattr(current_user, 'id') else None
                )
                
                # Store the API key temporarily in session to show to admin once
                from flask import session
                session['new_api_key'] = api_key_obj.key
                session['new_secret_key'] = api_key_obj.secret_key
                session['new_webhook_secret'] = api_key_obj.webhook_secret
                session['new_client_id'] = client.id
                
            except Exception as e:
                import logging
                logging.error(f"Failed to generate API key for client {client.id}: {str(e)}")
                # Continue anyway - admin can generate manually later
            
            db.session.commit()
            flash(_("Client and user account created successfully"), "success")
            return redirect(url_for("admin.view_client", client_id=client.id))
        except Exception as e:
            db.session.rollback()
            
            # Provide user-friendly error messages
            error_message = str(e)
            
            if 'UNIQUE constraint failed: users.username' in error_message:
                flash(f"Username '{form.username.data}' already exists. Please choose a different username.", "error")
            elif 'UNIQUE constraint failed: users.email' in error_message:
                flash(f"Email '{form.email.data}' is already registered. Please use a different email.", "error")
            elif 'UNIQUE constraint failed' in error_message:
                flash("A client with this information already exists. Please check the username, email, or other unique fields.", "error")
            elif 'NOT NULL constraint failed' in error_message:
                # Extract the column name from the error
                import re
                match = re.search(r'NOT NULL constraint failed: \w+\.(\w+)', error_message)
                field_name = match.group(1) if match else "required field"
                flash(f"Missing required field: {field_name}. Please fill in all required fields.", "error")
            else:
                # For other errors, show a generic message
                flash(f"Error creating client. Please check all fields and try again.", "error")
                # Log the full error for debugging
                import logging
                logging.error(f"Client creation error: {error_message}")
            
            return render_template("admin/client_form.html", form=form, client=None, title="Add Client")
    return render_template("admin/client_form.html", form=form, client=None, title="Add Client")

# --- Add Admin ---
@admin_bp.route("/admins/add", methods=["GET", "POST"])
@login_required
@superadmin_required
def add_admin():
    from app.forms import AdminForm
    from app.models import User, Role, AdminUser
    if form.validate_on_submit():
        try:
            # Get the selected role
            if form.admin_type.data == 'superadmin':
                admin_role = Role.query.filter_by(name='superadmin').first()
            else:
                admin_role = Role.query.filter_by(name='admin').first()

            if not admin_role:
                flash("Selected admin role not found", "error")
                return render_template("admin/admin_form.html", form=form, title="Add Admin")

            # Create User record for authentication
            user = User(
                username=form.username.data,
                email=form.email.data,
                role=admin_role
            )
            user.set_password(form.password.data)

            db.session.add(user)
            db.session.flush()  # Get user ID

            # Create AdminUser record with permissions
            admin_user = AdminUser(
                username=form.username.data,
                email=form.email.data,
                first_name=form.first_name.data,
                last_name=form.last_name.data,
                is_superuser=(form.admin_type.data == 'superadmin'),
                _active=form.is_active.data
            )
            admin_user.set_password(form.password.data)

            # Set permissions based on form checkboxes
            permissions = {
                'view_clients': form.perm_view_clients.data,
                'create_clients': form.perm_create_clients.data,
                'edit_clients': form.perm_edit_clients.data,
                'delete_clients': form.perm_delete_clients.data,
                'approve_payments': form.perm_approve_payments.data,
                'approve_withdrawals': form.perm_approve_withdrawals.data,
                'view_transactions': form.perm_view_transactions.data,
                'view_stats': form.perm_view_stats.data,
                'view_reports': form.perm_view_reports.data,
                'manage_wallet_providers': form.perm_manage_wallet_providers.data,
                'manage_bank_providers': form.perm_manage_bank_providers.data,
                'manage_admins': form.perm_manage_admins.data,
                'manage_api_keys': form.perm_manage_api_keys.data,
                'access_audit_logs': form.perm_access_audit_logs.data,
                'manage_settings': form.perm_manage_settings.data
            }

            # Update role permissions
            admin_role.permissions = permissions
            admin_role.description = f"Custom admin permissions for {form.username.data}"

            db.session.add(admin_user)
            db.session.commit()

            flash(f"Admin {form.username.data} created successfully", "success")
            return redirect(url_for("admin.list_admins"))

        except Exception as e:
            db.session.rollback()
            
            # Provide user-friendly error messages
            error_message = str(e)
            
            if 'UNIQUE constraint failed: users.username' in error_message:
                flash(f"Username '{form.username.data}' already exists. Please choose a different username.", "error")
            elif 'UNIQUE constraint failed: users.email' in error_message:
                flash(f"Email '{form.email.data}' is already registered. Please use a different email.", "error")
            elif 'UNIQUE constraint failed' in error_message:
                flash("An admin with this information already exists. Please check the username or email.", "error")
            elif 'NOT NULL constraint failed' in error_message:
                import re
                match = re.search(r'NOT NULL constraint failed: \w+\.(\w+)', error_message)
                field_name = match.group(1) if match else "required field"
                flash(f"Missing required field: {field_name}. Please fill in all required fields.", "error")
            else:
                flash(f"Error creating admin. Please check all fields and try again.", "error")
                import logging
                logging.error(f"Admin creation error: {error_message}")
            
            return render_template("admin/admin_create_form.html", form=form, title="Add Admin")

    return render_template("admin/admin_create_form.html", form=form, title="Add Admin")

# --- View All Admins ---
@admin_bp.route("/admins")
@login_required
@superadmin_required
def list_admins():
    from flask import request

    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '', type=str)

    # Build query - get admin users (not superadmins)
    from app.models import AdminUser
    query = AdminUser.query

    # Apply search filter
    if search:
        query = query.filter(AdminUser.username.contains(search) |
                           AdminUser.email.contains(search) |
                           AdminUser.first_name.contains(search) |
                           AdminUser.last_name.contains(search))

    # Get paginated results
    admins = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )

    return render_template(
        "admin/admins.html",
        admins=admins,
        search=search,
        per_page=per_page,
        current_admin=current_user,
    )

# --- View All Clients ---
@admin_bp.route("/clients")
@login_required
@superadmin_required
def list_clients():
    from flask import request
    
    # Get pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '', type=str)
    status = request.args.get('status', '', type=str)
    
    # Build query
    query = Client.query
    
    # Apply search filter
    if search:
        query = query.filter(Client.company_name.contains(search) | 
                           Client.email.contains(search))
    
    # Apply status filter
    if status:
        query = query.filter(Client.status == status)
    
    # Get paginated results
    clients = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    # Calculate statistics
    total_clients = Client.query.count()
    active_clients = Client.query.filter_by(is_active=True).count()
    verified_clients = Client.query.filter_by(is_verified=True).count()
    
    stats = {
        'total_clients': total_clients,
        'active_clients': active_clients,
        'verified_clients': verified_clients,
        'inactive_clients': total_clients - active_clients
    }
    
    return render_template("admin/clients/list.html", 
                         clients=clients, 
                         search=search, 
                         status=status, 
                         per_page=per_page,
                         stats=stats)




# View Client route
@admin_bp.route("/clients/<int:client_id>")
@login_required
@superadmin_required
def view_client(client_id):
    """View detailed client information"""
    client = Client.query.get_or_404(client_id)
    
    # Get client statistics
    from app.models import Payment
    total_payments = Payment.query.filter_by(client_id=client_id).count()
    completed_payments = Payment.query.filter_by(client_id=client_id, status='completed').count()
    total_amount = db.session.query(db.func.sum(Payment.amount)).filter_by(client_id=client_id, status='completed').scalar() or 0
    
    stats = {
        'total_payments': total_payments,
        'completed_payments': completed_payments,
        'total_amount': float(total_amount),
        'success_rate': (completed_payments / total_payments * 100) if total_payments > 0 else 0
    }
    
    return render_template("admin/clients/view.html", client=client, stats=stats)

# --- Edit Client ---
@admin_bp.route("/clients/<int:client_id>/edit", methods=["GET", "POST"])
@login_required
@superadmin_required
def edit_client(client_id):
    from app.models import ClientPackage
    client = Client.query.get_or_404(client_id)
    packages = ClientPackage.query.filter_by(status='ACTIVE').order_by(ClientPackage.id).all()
    
    form = ClientForm()
    # Set choices for package_id dropdown
    form.package_id.choices = [(p.id, p.name) for p in packages]
    
    if form.validate_on_submit():
        try:
            # Update client information
            client.company_name = form.company_name.data
            client.name = form.name.data
            client.email = form.email.data
            client.phone = form.phone.data
            client.website = form.website.data
            client.address = form.address.data
            client.city = form.city.data
            client.country = form.country.data
            client.postal_code = form.postal_code.data
            client.tax_id = form.tax_id.data
            client.vat_number = form.vat_number.data
            client.registration_number = form.registration_number.data
            client.contact_person = form.contact_person.data
            client.contact_email = form.contact_email.data
            client.contact_phone = form.contact_phone.data
            client.notes = form.notes.data
            client.rate_limit = form.rate_limit.data
            client.theme_color = form.theme_color.data
            client.deposit_commission_rate = form.deposit_commission_rate.data
            client.withdrawal_commission_rate = form.withdrawal_commission_rate.data
            client.balance = form.balance.data
            client.is_active = form.is_active.data
            client.is_verified = form.is_verified.data
            client.package_id = form.package_id.data
            
            # Update password if provided
            if form.new_password.data:
                client.set_password(form.new_password.data)
            
            db.session.commit()
            flash(_("Client updated successfully"), "success")
            return redirect(url_for("admin.view_client", client_id=client_id))
        except Exception as e:
            db.session.rollback()
            
            # Provide user-friendly error messages
            error_message = str(e)
            
            if 'UNIQUE constraint failed: users.email' in error_message:
                flash(f"Email '{form.email.data}' is already in use by another user. Please use a different email.", "error")
            elif 'UNIQUE constraint failed' in error_message:
                flash("This information conflicts with an existing record. Please check the email or other unique fields.", "error")
            elif 'NOT NULL constraint failed' in error_message:
                import re
                match = re.search(r'NOT NULL constraint failed: \w+\.(\w+)', error_message)
                field_name = match.group(1) if match else "required field"
                flash(f"Missing required field: {field_name}. Please fill in all required fields.", "error")
            else:
                flash(f"Error updating client. Please check all fields and try again.", "error")
                import logging
                logging.error(f"Client update error: {error_message}")
    
    # Pre-populate form with existing client data
    if request.method == "GET":
        form.company_name.data = client.company_name
        form.name.data = client.name
        form.email.data = client.email
        form.phone.data = client.phone
        form.website.data = client.website
        form.address.data = client.address
        form.city.data = client.city
        form.country.data = client.country
        form.postal_code.data = client.postal_code
        form.tax_id.data = client.tax_id
        form.vat_number.data = client.vat_number
        form.registration_number.data = client.registration_number
        form.contact_person.data = client.contact_person
        form.contact_email.data = client.contact_email
        form.contact_phone.data = client.contact_phone
        form.notes.data = client.notes
        form.rate_limit.data = client.rate_limit
        form.theme_color.data = client.theme_color
        form.deposit_commission_rate.data = client.deposit_commission_rate
        form.withdrawal_commission_rate.data = client.withdrawal_commission_rate
        form.balance.data = client.balance
        form.is_active.data = client.is_active
        form.is_verified.data = client.is_verified
        form.package_id.data = client.package_id
    
    return render_template("admin/client_form.html", form=form, client=client, title="Edit Client")


# --- Delete Client ---
@admin_bp.route("/clients/<int:client_id>/delete", methods=["POST"])
@login_required
@superadmin_required
def delete_client(client_id):
    client = Client.query.get_or_404(client_id)
    db.session.delete(client)
    db.session.commit()
    flash("Client deleted", "info")
    return redirect(url_for("admin.list_clients"))


@admin_bp.route('/payment-sessions')
@login_required
@superadmin_required
def payment_sessions_list():
    from sqlalchemy import func, or_
    from app.models.payment_session import PaymentSession

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    per_page = max(1, min(per_page, 100))

    status_filter = request.args.get('status')
    client_id_filter = request.args.get('client_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search', '').strip()

    query = PaymentSession.query.join(Client, PaymentSession.client_id == Client.id)

    if status_filter:
        query = query.filter(PaymentSession.status == status_filter)

    if client_id_filter:
        query = query.filter(PaymentSession.client_id == client_id_filter)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            query = query.filter(PaymentSession.created_at >= start_dt)
        except ValueError:
            flash('Invalid start date format. Use YYYY-MM-DD.', 'warning')

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(PaymentSession.created_at < end_dt)
        except ValueError:
            flash('Invalid end date format. Use YYYY-MM-DD.', 'warning')

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                PaymentSession.public_id.ilike(like),
                PaymentSession.order_id.ilike(like),
                PaymentSession.customer_email.ilike(like)
            )
        )

    ordered_query = query.order_by(PaymentSession.created_at.desc())
    sessions = ordered_query.paginate(page=page, per_page=per_page, error_out=False)

    filtered_query = query.order_by(None)
    total_sessions = filtered_query.count()
    status_rows = filtered_query.with_entities(PaymentSession.status, func.count()).group_by(PaymentSession.status).all()
    status_counts = {status: count for status, count in status_rows}

    stats = {
        'total_sessions': total_sessions,
        'created': status_counts.get('created', 0),
        'pending': status_counts.get('pending', 0),
        'completed': status_counts.get('completed', 0),
        'failed': status_counts.get('failed', 0),
    }

    clients = Client.query.filter_by(is_active=True).order_by(Client.company_name.asc()).all()

    status_badges = {
        'created': 'secondary',
        'pending': 'info',
        'completed': 'success',
        'failed': 'danger',
    }

    return render_template(
        'admin/payment_sessions.html',
        sessions=sessions,
        stats=stats,
        clients=clients,
        status_badges=status_badges,
    )


@admin_bp.route('/payment-sessions/<int:session_id>')
@login_required
@superadmin_required
def view_payment_session(session_id):
    from sqlalchemy.orm import joinedload
    from app.models.payment_session import PaymentSession
    from app.models.payment import Payment

    session = (
        PaymentSession.query.options(
            joinedload(PaymentSession.client),
            joinedload(PaymentSession.events)
        ).get_or_404(session_id)
    )

    related_payment = Payment.query.filter_by(transaction_id=session.public_id).first()

    recent_sessions = (
        PaymentSession.query
        .filter(
            PaymentSession.client_id == session.client_id,
            PaymentSession.id != session.id
        )
        .order_by(PaymentSession.created_at.desc())
        .limit(5)
        .all()
    )

    status_badges = {
        'created': 'secondary',
        'pending': 'info',
        'completed': 'success',
        'failed': 'danger',
    }

    return render_template(
        'admin/payment_session_detail.html',
        session=session,
        payment=related_payment,
        recent_sessions=recent_sessions,
        status_badges=status_badges,
    )
    
# Payments list route
@admin_bp.route('/payments')
@login_required
@superadmin_required
def payments_list():
    """List and manage payments with filtering and pagination"""
    from app.models import Payment, Client
    from sqlalchemy import func, and_, or_
    
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    status_filter = request.args.get('status')
    client_id_filter = request.args.get('client_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    search = request.args.get('search')

    # Base query
    base_query = Payment.query.join(Client, Payment.client_id == Client.id)

    # Apply filters
    status_enum = None
    if status_filter:
        try:
            status_enum = PaymentStatus(status_filter)
        except ValueError:
            status_enum = None
    if status_enum:
        base_query = base_query.filter(Payment._status == status_enum)

    if client_id_filter:
        base_query = base_query.filter(Payment.client_id == client_id_filter)

    if start_date:
        try:
            start_dt = datetime.strptime(start_date, '%Y-%m-%d')
            base_query = base_query.filter(Payment.created_at >= start_dt)
        except ValueError:
            pass

    if end_date:
        try:
            end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
            base_query = base_query.filter(Payment.created_at < end_dt)
        except ValueError:
            pass

    if search:
        search_term = f"%{search}%"
        base_query = base_query.filter(
            or_(
                Payment.transaction_id.ilike(search_term),
                Client.company_name.ilike(search_term),
                Client.name.ilike(search_term),
                Client.email.ilike(search_term)
            )
        )

    # Order by creation date (newest first)
    ordered_query = base_query.order_by(Payment.created_at.desc())

    # Paginate results
    payments = ordered_query.paginate(page=page, per_page=per_page, error_out=False)

    # Get all clients for filter dropdown
    clients = Client.query.filter_by(is_active=True).all()

    # Calculate statistics using filtered query
    total_payments = base_query.count()

    completed_filter_query = base_query.filter(Payment._status == PaymentStatus.COMPLETED)
    total_volume = completed_filter_query.with_entities(func.coalesce(func.sum(Payment.fiat_amount), 0)).scalar() or 0
    avg_transaction = (total_volume / total_payments) if total_payments > 0 else 0
    completed_count = completed_filter_query.count()
    success_rate = (completed_count / total_payments) if total_payments > 0 else 0

    stats = {
        'total_payments': total_payments,
        'total_volume': float(total_volume),
        'avg_transaction': float(avg_transaction),
        'success_rate': success_rate
    }
    
    return render_template(
        'admin/payments.html',
        payments=payments,
        clients=clients,
        stats=stats,
        selected_client_id=client_id_filter,
        selected_status=status_filter,
        selected_start_date=start_date,
        selected_end_date=end_date,
        search_term=search
    )

# Wallet Providers route
@admin_bp.route('/wallet-providers')
@login_required
@superadmin_required
def wallet_providers():
    from app.models import WalletProvider, WalletBalance

    # Get all providers
    providers = WalletProvider.query.order_by(WalletProvider.priority.asc()).all()

    # Get balances for each provider
    provider_balances = {}
    for provider in providers:
        balances = WalletBalance.query.filter_by(provider_id=provider.id).all()
        if balances:
            provider_balances[provider.id] = {
                balance.currency: float(balance.total_balance)
                for balance in balances
            }

    return render_template('admin/wallet_providers.html',
                         providers=providers,
                         provider_balances=provider_balances)

# Wallet History route
@admin_bp.route('/wallet-history')
@login_required
@superadmin_required
def wallet_history():
    # Add logic to fetch and display wallet history
    return render_template('admin/wallet_history.html')

# Wallet Balances route
@admin_bp.route('/wallet-balances')
@login_required
@superadmin_required
def wallet_balances():
    # Add logic to fetch and display wallet balances
    return render_template('admin/wallet_balances.html')

# ============================================================================
# CLIENT WALLET MANAGEMENT (Branch & Admin)
# ============================================================================

@admin_bp.route('/client-wallets')
@login_required
@admin_required
def client_wallets():
    """View all client wallet configurations with branch isolation"""
    from app.models import ClientWallet, Client
    from sqlalchemy import func
    
    # Get current admin's branch
    branch_id = g.get('branch_id')
    
    # Base query with branch isolation
    query = db.session.query(
        ClientWallet,
        Client.company_name,
        Client.contact_email
    ).join(Client, ClientWallet.client_id == Client.id)
    
    # Apply branch isolation for non-owners
    if not current_user.is_owner():
        query = query.filter(Client.branch_id == branch_id)
    
    # Get filter parameters
    client_id = request.args.get('client_id', type=int)
    wallet_type = request.args.get('wallet_type')
    status = request.args.get('status')
    
    if client_id:
        query = query.filter(ClientWallet.client_id == client_id)
    if wallet_type:
        query = query.filter(ClientWallet.wallet_type == wallet_type)
    if status:
        query = query.filter(ClientWallet.status == status)
    
    wallets = query.order_by(ClientWallet.created_at.desc()).all()
    
    # Get statistics
    stats_query = db.session.query(
        func.count(ClientWallet.id).label('total'),
        func.count(ClientWallet.id).filter(ClientWallet.status == 'active').label('active'),
        func.count(ClientWallet.id).filter(ClientWallet.status == 'pending_verification').label('pending')
    ).join(Client, ClientWallet.client_id == Client.id)
    
    if not current_user.is_owner():
        stats_query = stats_query.filter(Client.branch_id == branch_id)
    
    stats = stats_query.first()
    
    # Get clients for filter dropdown
    clients_query = Client.query
    if not current_user.is_owner():
        clients_query = clients_query.filter_by(branch_id=branch_id)
    clients = clients_query.order_by(Client.company_name).all()
    
    return render_template('admin/client_wallets.html',
                         wallets=wallets,
                         clients=clients,
                         stats=stats)

@admin_bp.route('/client-wallets/<int:wallet_id>')
@login_required
@admin_required
def view_client_wallet(wallet_id):
    """View detailed wallet configuration"""
    from app.models import ClientWallet, Client
    from flask import jsonify
    
    # Get wallet with branch check
    wallet = db.session.query(ClientWallet).join(Client).filter(
        ClientWallet.id == wallet_id
    )
    
    # Apply branch isolation
    if not current_user.is_owner():
        branch_id = g.get('branch_id')
        wallet = wallet.filter(Client.branch_id == branch_id)
    
    wallet = wallet.first()
    
    if not wallet:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'error': 'Wallet not found'}), 404
        flash('Wallet not found', 'danger')
        return redirect(url_for('admin.client_wallets'))
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        wallet_data = wallet.to_dict()
        wallet_data['wallet_addresses'] = wallet.wallet_addresses or {}
        wallet_data['client_name'] = wallet.client.company_name
        return jsonify({'success': True, 'wallet': wallet_data}), 200
    
    return render_template('admin/view_client_wallet.html', wallet=wallet)

@admin_bp.route('/client-wallets/<int:wallet_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_client_wallet(wallet_id):
    """Approve a pending wallet configuration"""
    from app.models import ClientWallet, Client, WalletStatus
    from flask import jsonify
    
    # Get wallet with branch check
    wallet = db.session.query(ClientWallet).join(Client).filter(
        ClientWallet.id == wallet_id
    )
    
    # Apply branch isolation
    if not current_user.is_owner():
        branch_id = g.get('branch_id')
        wallet = wallet.filter(Client.branch_id == branch_id)
    
    wallet = wallet.first()
    
    if not wallet:
        return jsonify({'success': False, 'error': 'Wallet not found'}), 404
    
    try:
        # Validate wallet configuration
        validation = wallet.validate_addresses()
        if not validation['valid'] and wallet.wallet_type.value == 'custom_manual':
            return jsonify({
                'success': False,
                'error': 'Wallet validation failed',
                'details': validation['errors']
            }), 400
        
        wallet.status = WalletStatus.ACTIVE
        wallet.error_message = None
        db.session.commit()
        
        flash(f"Wallet '{wallet.wallet_name}' approved successfully", 'success')
        return jsonify({
            'success': True,
            'message': f"Wallet '{wallet.wallet_name}' approved"
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

@admin_bp.route('/client-wallets/<int:wallet_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_client_wallet(wallet_id):
    """Reject a pending wallet configuration"""
    from app.models import ClientWallet, Client, WalletStatus
    from flask import jsonify
    
    # Get wallet with branch check
    wallet = db.session.query(ClientWallet).join(Client).filter(
        ClientWallet.id == wallet_id
    )
    
    # Apply branch isolation
    if not current_user.is_owner():
        branch_id = g.get('branch_id')
        wallet = wallet.filter(Client.branch_id == branch_id)
    
    wallet = wallet.first()
    
    if not wallet:
        return jsonify({'success': False, 'error': 'Wallet not found'}), 404
    
    try:
        reason = request.get_json().get('reason', 'Configuration rejected by admin')
        
        wallet.status = WalletStatus.ERROR
        wallet.error_message = reason
        db.session.commit()
        
        flash(f"Wallet '{wallet.wallet_name}' rejected", 'warning')
        return jsonify({
            'success': True,
            'message': f"Wallet '{wallet.wallet_name}' rejected"
        }), 200
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400

# Create Wallet Provider route
@admin_bp.route('/create-wallet-provider', methods=['GET', 'POST'])
@login_required
@superadmin_required
def create_wallet_provider():
    # Add logic to create a new wallet provider
    if request.method == 'POST':
        # Handle form submission
        pass
    return render_template('admin/create_wallet_provider.html')

# Edit Wallet Provider route
@admin_bp.route('/edit-wallet-provider/<int:provider_id>', methods=['GET', 'POST'])
@login_required
@superadmin_required
def edit_wallet_provider(provider_id):
    # Add logic to edit a wallet provider
    if request.method == 'POST':
        # Handle form submission
        pass
    return render_template('admin/edit_wallet_provider.html', provider_id=provider_id)

# Test Wallet Connection route
@admin_bp.route('/test-wallet-connection/<int:provider_id>', methods=['POST'])
@login_required
@superadmin_required
def test_wallet_connection(provider_id):
    from app.utils.wallet_api import WalletService

    try:
        success, message = WalletService.test_provider_connection(provider_id)

        if success:
            flash('Wallet connection successful!', 'success')
            return jsonify({'success': True, 'message': message})
        else:
            flash(f'Wallet connection failed: {message}', 'danger')
            return jsonify({'success': False, 'message': message})

    except Exception as e:
        error_msg = f'Connection test failed: {str(e)}'
        flash(error_msg, 'danger')
        return jsonify({'success': False, 'message': error_msg})

# Sync Wallet Balances route
@admin_bp.route('/sync-wallet-balances/<int:provider_id>', methods=['POST'])
@login_required
@superadmin_required
def sync_wallet_balances(provider_id):
    from app.utils.wallet_api import WalletService

    try:
        balances = WalletService.get_provider_balance(provider_id)
        flash('Wallet balances synced successfully!', 'success')
        return jsonify({'success': True, 'balances': balances})

    except Exception as e:
        error_msg = f'Balance sync failed: {str(e)}'
        flash(error_msg, 'danger')
        return jsonify({'success': False, 'message': error_msg})

# Set Primary Wallet Provider route
@admin_bp.route('/set-primary-wallet-provider/<int:provider_id>', methods=['POST'])
@login_required
@superadmin_required
def set_primary_wallet_provider(provider_id):
    try:
        provider = WalletProvider.query.get_or_404(provider_id)

        # Remove primary from all providers
        WalletProvider.query.update({'is_primary': False})

        # Set this provider as primary
        provider.is_primary = True
        db.session.commit()

        flash(f'{provider.name} set as primary wallet provider!', 'success')
        return jsonify({'success': True, 'message': f'{provider.name} set as primary'})

    except Exception as e:
        error_msg = f'Failed to set primary provider: {str(e)}'
        flash(error_msg, 'danger')
        return jsonify({'success': False, 'message': error_msg})

# Delete Wallet Provider route
@admin_bp.route('/delete-wallet-provider/<int:provider_id>', methods=['DELETE'])
@login_required
@superadmin_required
def delete_wallet_provider(provider_id):
    try:
        provider = WalletProvider.query.get_or_404(provider_id)

        # Don't allow deletion of primary provider
        if provider.is_primary:
            flash('Cannot delete primary wallet provider!', 'danger')
            return jsonify({'success': False, 'message': 'Cannot delete primary provider'})

        db.session.delete(provider)
        db.session.commit()

        flash(f'Wallet provider {provider.name} deleted successfully!', 'success')
        return jsonify({'success': True, 'message': f'Provider {provider.name} deleted'})

    except Exception as e:
        error_msg = f'Failed to delete provider: {str(e)}'
        flash(error_msg, 'danger')
        return jsonify({'success': False, 'message': error_msg})

# Audit Trail route
@admin_bp.route('/audit-trail')
@login_required
@superadmin_required
def audit_trail():
    from app.models.audit import AuditTrail, AuditActionType
    from app.models import User
    
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    action_type = request.args.get('action_type')
    entity_type = request.args.get('entity_type')
    user_id = request.args.get('user_id', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Base query with user join
    query = AuditTrail.query.join(User, AuditTrail.user_id == User.id)
    
    # Apply filters
    if action_type:
        query = query.filter(AuditTrail.action_type == action_type)
    
    if entity_type:
        query = query.filter(AuditTrail.entity_type == entity_type)
    
    if user_id:
        query = query.filter(AuditTrail.user_id == user_id)
    
    if start_date:
        query = query.filter(AuditTrail.created_at >= start_date)
    
    if end_date:
        # Add one day to include the end date fully
        from datetime import datetime, timedelta
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(AuditTrail.created_at < end_date_obj)
    
    # Order by creation date (newest first)
    query = query.order_by(AuditTrail.created_at.desc())
    
    # Paginate results
    audit_logs = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get all users for filter dropdown
    users = User.query.filter_by(is_active=True).all()
    
    return render_template('admin/audit_trail.html',
                         audit_logs=audit_logs,
                         users=users,
                         AuditActionType=AuditActionType)

# ========================
# SECURITY & LOGIN HISTORY
# ========================

@admin_bp.route('/security/login-history')
@login_required
@superadmin_required
def login_history():
    """View login history for all users"""
    from app.models.login_history import LoginHistory
    
    page = request.args.get('page', 1, type=int)
    user_type = request.args.get('user_type')
    success = request.args.get('success')
    search = request.args.get('search', '').strip()
    
    query = LoginHistory.query
    
    # Apply filters
    if user_type:
        query = query.filter_by(user_type=user_type)
    
    if success is not None:
        query = query.filter_by(success=(success == '1'))
    
    if search:
        query = query.filter(
            db.or_(
                LoginHistory.username.ilike(f'%{search}%'),
                LoginHistory.ip_address.ilike(f'%{search}%')
            )
        )
    
    logs = query.order_by(LoginHistory.login_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    # Get statistics
    total_logins = LoginHistory.query.filter_by(success=True).count()
    failed_logins = LoginHistory.query.filter_by(success=False).count()
    suspicious_activity = LoginHistory.get_suspicious_activity()
    
    return render_template('admin/security/login_history.html',
                         logs=logs,
                         total_logins=total_logins,
                         failed_logins=failed_logins,
                         suspicious_activity=suspicious_activity)

@admin_bp.route('/security/login-history/user/<int:user_id>')
@login_required
@superadmin_required
def user_login_history(user_id):
    """View login history for specific user"""
    from app.models.login_history import LoginHistory
    
    user = User.query.get_or_404(user_id)
    history = LoginHistory.get_user_history(user_id, limit=100)
    
    return render_template('admin/security/user_login_history.html',
                         user=user,
                         history=history)

@admin_bp.route('/security/login-history/details/<int:log_id>')
@login_required
@superadmin_required
def login_history_details(log_id):
    """Get details of a specific login attempt (AJAX)"""
    from app.models.login_history import LoginHistory
    
    log = LoginHistory.query.get_or_404(log_id)
    return jsonify(log.to_dict())

@admin_bp.route('/security/login-history/export')
@login_required
@superadmin_required
def export_login_history():
    """Export login history to CSV"""
    from app.models.login_history import LoginHistory
    import csv
    from io import StringIO
    from flask import Response
    
    # Get filtered data
    logs = LoginHistory.get_recent_logins(hours=720, limit=10000)  # Last 30 days
    
    # Create CSV
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['Login Time', 'Username', 'User Type', 'Status', 'IP Address', 
                    'Location', 'Session Duration (min)', 'Failure Reason'])
    
    for log in logs:
        writer.writerow([
            log.login_at.strftime('%Y-%m-%d %H:%M:%S'),
            log.username,
            log.user_type,
            'Success' if log.success else 'Failed',
            log.ip_address,
            f"{log.city}, {log.country}" if log.city and log.country else 'Unknown',
            log.get_session_duration() or 'N/A',
            log.failure_reason or ''
        ])
    
    output = si.getvalue()
    si.close()
    
    return Response(
        output,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=login_history.csv'}
    )

# Access Control route
@admin_bp.route('/access-control')
@login_required
@superadmin_required
def access_control():
    # Add logic to fetch and display access control
    return render_template('admin/access_control.html')

# Settings route
@admin_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@superadmin_required
def settings():
    from app.models.setting import Setting
    from app.forms import build_settings_form

    # Create default settings if they don't exist
    Setting.create_default_settings()

    # Get all settings grouped by type
    all_settings = Setting.get_all_settings()

    # Flatten settings for dynamic form field generation
    settings_data = [setting for setting_list in all_settings.values() for setting in setting_list]

    # Build dynamic form with available settings
    form = build_settings_form(settings_data=settings_data)

    if request.method == 'POST' and form.validate_on_submit():
        # Handle form submission
        setting_type = request.form.get('setting_type')
        for key, value in request.form.items():
            if key not in ['csrf_token', 'setting_type', 'submit']:
                Setting.update_setting(key, value)
        flash('Settings updated successfully!', 'success')
        return redirect(url_for('admin.settings'))

    # Create settings object with attributes for template
    class SettingsObject:
        def __init__(self, settings_dict):
            for key, value in settings_dict.items():
                setattr(self, key, value)

    settings_obj = SettingsObject(all_settings)

    return render_template('admin/settings.html', form=form, settings=settings_obj)

# Support Tickets route
@admin_bp.route('/support-tickets')
@login_required
@superadmin_required
def support_tickets():
    """View and manage support tickets"""
    from app.models.support_ticket import SupportTicket
    from app.models import User
    
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    status = request.args.get('status')
    user_id = request.args.get('user_id', type=int)
    search = request.args.get('search')
    
    # Base query with user join (optional)
    query = SupportTicket.query.outerjoin(User, SupportTicket.user_id == User.id)
    
    # Apply filters
    if status:
        query = query.filter(SupportTicket.status == status)
    
    if user_id:
        query = query.filter(SupportTicket.user_id == user_id)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                SupportTicket.subject.ilike(search_term),
                SupportTicket.description.ilike(search_term)
            )
        )
    
    # Order by creation date (newest first)
    query = query.order_by(SupportTicket.created_at.desc())
    
    # Paginate results
    tickets = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get all users for filter dropdown
    users = User.query.filter_by(is_active=True).all()
    
    # Calculate statistics
    total_tickets = SupportTicket.query.count()
    open_tickets = SupportTicket.query.filter_by(status='open').count()
    closed_tickets = SupportTicket.query.filter_by(status='closed').count()
    pending_tickets = SupportTicket.query.filter_by(status='pending').count()
    
    stats = {
        'total_tickets': total_tickets,
        'open_tickets': open_tickets,
        'closed_tickets': closed_tickets,
        'pending_tickets': pending_tickets,
        'resolution_rate': (closed_tickets / total_tickets * 100) if total_tickets > 0 else 0
    }
    
    return render_template('admin/support_tickets.html',
                         tickets=tickets,
                         users=users,
                         stats=stats)

# API Docs route
@admin_bp.route('/api-docs')
@login_required
@superadmin_required
def api_docs():
    # Add logic to fetch and display API documentation
    return render_template('admin/api_docs.html')


# ========================
# BANK GATEWAY MANAGEMENT
# ========================

@admin_bp.route('/bank-gateway')
@login_required
@superadmin_required
def bank_gateway_dashboard():
    """Bank gateway overview within main admin panel"""
    # Statistics
    total_providers = BankGatewayProvider.query.count()
    total_accounts = BankGatewayAccount.query.count()
    total_clients = BankGatewayClientSite.query.count()
    
    # Recent transactions
    recent_transactions = BankGatewayTransaction.query.order_by(
        BankGatewayTransaction.created_at.desc()
    ).limit(10).all()
    
    # Pending transactions requiring admin attention
    pending_transactions = BankGatewayTransaction.query.filter_by(
        status='pending'
    ).count()
    
    # Revenue statistics (last 30 days)
    last_month = now_eest() - timedelta(days=30)
    monthly_revenue = db.session.query(
        db.func.sum(BankGatewayTransaction.commission_amount)
    ).filter(
        BankGatewayTransaction.created_at >= last_month,
        BankGatewayTransaction.status == 'confirmed'
    ).scalar() or 0
    
    return render_template('admin/bank_gateway/dashboard.html',
                         total_providers=total_providers,
                         total_accounts=total_accounts,
                         total_clients=total_clients,
                         recent_transactions=recent_transactions,
                         pending_transactions=pending_transactions,
                         monthly_revenue=monthly_revenue)

@admin_bp.route('/bank-gateway/providers')
@login_required
@superadmin_required
def bank_providers():
    """Manage bank gateway providers"""
    providers = BankGatewayProvider.query.all()
    return render_template('admin/bank_gateway/providers.html', providers=providers)

@admin_bp.route('/bank-gateway/providers/add', methods=['GET', 'POST'])
@login_required
@superadmin_required
def add_bank_provider():
    """Add new bank gateway provider"""
    if request.method == 'POST':
        user_id = request.form.get('user_id')
        bank_name = request.form.get('bank_name')
        
        provider = BankGatewayProvider(
            user_id=user_id,
            bank_name=bank_name,
            status='active'
        )
        
        db.session.add(provider)
        db.session.commit()
        
        flash('Bank provider added successfully!', 'success')
        return redirect(url_for('admin.bank_providers'))
    
    users = User.query.all()
    return render_template('admin/bank_gateway/add_provider.html', users=users)

@admin_bp.route('/bank-gateway/providers/<int:provider_id>/toggle_block', methods=['POST'])
@login_required
@superadmin_required
def toggle_bank_provider_block(provider_id):
    """Block/unblock bank provider"""
    provider = BankGatewayProvider.query.get_or_404(provider_id)
    provider.is_blocked = not provider.is_blocked
    db.session.commit()
    
    status = 'blocked' if provider.is_blocked else 'unblocked'
    flash(f'Provider {status} successfully!', 'success')
    return redirect(url_for('admin.bank_providers'))

@admin_bp.route('/bank-gateway/accounts')
@login_required
@superadmin_required
def bank_accounts():
    """Manage bank accounts"""
    accounts = BankGatewayAccount.query.all()
    providers = BankGatewayProvider.query.all()
    return render_template('admin/bank_gateway/accounts.html', 
                         accounts=accounts,
                         providers=providers)

@admin_bp.route('/bank-gateway/transactions')
@login_required
@superadmin_required
def bank_transactions():
    """Manage bank gateway transactions"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', '')
    
    query = BankGatewayTransaction.query
    
    if status:
        query = query.filter_by(status=status)
    
    transactions = query.order_by(BankGatewayTransaction.created_at.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    return render_template('admin/bank_gateway/transactions.html', 
                         transactions=transactions, status=status)

@admin_bp.route('/bank-gateway/transaction/<int:transaction_id>')
@login_required
@superadmin_required
def bank_transaction_detail(transaction_id):
    """View bank transaction details"""
    transaction = BankGatewayTransaction.query.get_or_404(transaction_id)
    return render_template('admin/bank_gateway/transaction_detail.html', 
                         transaction=transaction)

@admin_bp.route('/bank-gateway/clients')
@login_required
@superadmin_required
def bank_clients():
    """Manage bank gateway clients"""
    client_sites = BankGatewayClientSite.query.all()
    clients = Client.query.all()
    return render_template('admin/bank_gateway/clients.html', 
                         client_sites=client_sites,
                         clients=clients)

@admin_bp.route('/bank-gateway/clients/add', methods=['GET', 'POST'])
@login_required
@superadmin_required
def add_bank_client():
    """Add new bank gateway client"""
    if request.method == 'POST':
        client_id = request.form.get('client_id')
        site_name = request.form.get('site_name')
        site_url = request.form.get('site_url')
        
        # Create API key
        api_key = secrets.token_urlsafe(32)
        
        bank_client = BankGatewayClientSite(
            client_id=client_id,
            site_name=site_name,
            site_url=site_url,
            api_key=api_key,
            is_active=True
        )
        
        db.session.add(bank_client)
        db.session.commit()
        
        flash('Bank client added successfully!', 'success')
        return redirect(url_for('admin.bank_clients'))
    
    clients = Client.query.all()
    return render_template('admin/bank_gateway/add_client.html', clients=clients)

@admin_bp.route('/bank-gateway/reports')
@login_required
@superadmin_required
def bank_reports():
    """Bank gateway reports and analytics"""
    end_date = now_eest()
    start_date = end_date - timedelta(days=30)

    # Daily transaction statistics
    daily_stats = db.session.query(
        db.func.date(BankGatewayTransaction.created_at).label('date'),
        db.func.count(BankGatewayTransaction.id).label('count'),
        db.func.sum(BankGatewayTransaction.amount).label('total_amount'),
        db.func.sum(BankGatewayTransaction.commission_amount).label('total_commission')
    ).filter(
        BankGatewayTransaction.created_at >= start_date,
        BankGatewayTransaction.created_at <= end_date,
        BankGatewayTransaction.status.in_(['pending', 'confirmed', 'completed', 'approved', 'rejected'])
    ).group_by(
        db.func.date(BankGatewayTransaction.created_at)
    ).order_by(db.func.date(BankGatewayTransaction.created_at)).all()

    daily_labels = [stat.date.strftime('%Y-%m-%d') for stat in daily_stats]
    daily_volumes = [float(stat.total_amount or 0) for stat in daily_stats]

    total_deposits = db.session.query(
        db.func.coalesce(db.func.sum(BankGatewayTransaction.amount), 0)
    ).filter(
        BankGatewayTransaction.transaction_type == 'deposit',
        BankGatewayTransaction.status.in_(['confirmed', 'completed', 'approved']),
        BankGatewayTransaction.created_at >= start_date,
        BankGatewayTransaction.created_at <= end_date,
    ).scalar() or 0

    deposit_count = db.session.query(
        db.func.count(BankGatewayTransaction.id)
    ).filter(
        BankGatewayTransaction.transaction_type == 'deposit',
        BankGatewayTransaction.status.in_(['confirmed', 'completed', 'approved']),
        BankGatewayTransaction.created_at >= start_date,
        BankGatewayTransaction.created_at <= end_date,
    ).scalar() or 0

    total_withdrawals = db.session.query(
        db.func.coalesce(db.func.sum(BankGatewayTransaction.amount), 0)
    ).filter(
        BankGatewayTransaction.transaction_type == 'withdraw',
        BankGatewayTransaction.status.in_(['confirmed', 'completed', 'approved']),
        BankGatewayTransaction.created_at >= start_date,
        BankGatewayTransaction.created_at <= end_date,
    ).scalar() or 0

    withdrawal_count = db.session.query(
        db.func.count(BankGatewayTransaction.id)
    ).filter(
        BankGatewayTransaction.transaction_type == 'withdraw',
        BankGatewayTransaction.status.in_(['confirmed', 'completed', 'approved']),
        BankGatewayTransaction.created_at >= start_date,
        BankGatewayTransaction.created_at <= end_date,
    ).scalar() or 0

    total_commissions = db.session.query(
        db.func.coalesce(db.func.sum(BankGatewayTransaction.commission_amount), 0)
    ).filter(
        BankGatewayTransaction.status.in_(['confirmed', 'completed', 'approved']),
        BankGatewayTransaction.created_at >= start_date,
        BankGatewayTransaction.created_at <= end_date,
    ).scalar() or 0

    commission_count = db.session.query(
        db.func.count(BankGatewayTransaction.id)
    ).filter(
        BankGatewayTransaction.status.in_(['confirmed', 'completed', 'approved']),
        BankGatewayTransaction.commission_amount.isnot(None),
        BankGatewayTransaction.created_at >= start_date,
        BankGatewayTransaction.created_at <= end_date,
    ).scalar() or 0

    net_revenue = float(total_deposits or 0) - float(total_commissions or 0)

    provider_stats = db.session.query(
        BankGatewayProvider,
        db.func.count(BankGatewayTransaction.id).label('transaction_count'),
        db.func.coalesce(db.func.sum(BankGatewayTransaction.amount), 0).label('total_amount'),
        db.func.coalesce(db.func.sum(BankGatewayTransaction.provider_commission), 0).label('commission_earned'),
        db.func.coalesce(db.func.sum(
            db.case((BankGatewayTransaction.status.in_(['confirmed', 'completed', 'approved']), 1), else_=0)
        ), 0).label('success_count'),
        db.func.coalesce(db.func.sum(
            db.case((BankGatewayTransaction.status == 'pending', 1), else_=0)
        ), 0).label('pending_count'),
        db.func.coalesce(db.func.sum(
            db.case((BankGatewayTransaction.status == 'rejected', 1), else_=0)
        ), 0).label('rejected_count'),
        db.func.avg(
            db.case(
                (BankGatewayTransaction.confirmed_at.isnot(None),
                 db.func.extract('epoch', BankGatewayTransaction.confirmed_at - BankGatewayTransaction.created_at))
            )
        ).label('avg_processing_time')
    ).outerjoin(
        BankGatewayTransaction,
        db.and_(
            BankGatewayTransaction.provider_id == BankGatewayProvider.id,
            BankGatewayTransaction.created_at >= start_date,
            BankGatewayTransaction.created_at <= end_date,
        )
    ).group_by(BankGatewayProvider.id).all()

    site_stats = db.session.query(
        BankGatewayClientSite,
        db.func.coalesce(
            db.func.sum(
                db.case(
                    (BankGatewayTransaction.transaction_type == 'deposit', BankGatewayTransaction.amount),
                    else_=0
                )
            ), 0
        ).label('total_deposits'),
        db.func.coalesce(
            db.func.sum(
                db.case(
                    (BankGatewayTransaction.transaction_type == 'withdraw', BankGatewayTransaction.amount),
                    else_=0
                )
            ), 0
        ).label('total_withdrawals'),
        db.func.coalesce(db.func.sum(BankGatewayTransaction.commission_amount), 0).label('commission_paid')
    ).outerjoin(
        BankGatewayTransaction,
        db.and_(
            BankGatewayTransaction.client_site_id == BankGatewayClientSite.id,
            BankGatewayTransaction.created_at >= start_date,
            BankGatewayTransaction.created_at <= end_date,
        )
    ).group_by(BankGatewayClientSite.id).all()

    clients = Client.query.order_by(Client.company_name).all()

    status_counts = db.session.query(
        BankGatewayTransaction.status,
        db.func.count(BankGatewayTransaction.id)
    ).filter(
        BankGatewayTransaction.created_at >= start_date,
        BankGatewayTransaction.created_at <= end_date,
    ).group_by(BankGatewayTransaction.status).all()

    status_count_map = {status: count for status, count in status_counts}

    completed_count = status_count_map.get('completed', 0)
    pending_count = status_count_map.get('pending', 0)
    rejected_count = status_count_map.get('rejected', 0)

    provider_stat_rows = []
    for provider, txn_count, total_amount, commission_earned, avg_processing_seconds in provider_stats:
        success_total = status_count_map.get('completed', 0)
        total_transactions = status_count_map.get('completed', 0) + status_count_map.get('pending', 0) + status_count_map.get('rejected', 0)
        success_rate = 0
        if total_transactions:
            success_rate = (success_total / total_transactions) * 100

        provider_stat_rows.append(SimpleNamespace(
            bank_name=provider.name,
            first_name=getattr(provider.user, 'first_name', ''),
            last_name=getattr(provider.user, 'last_name', ''),
            transaction_count=txn_count or 0,
            total_amount=float(total_amount or 0),
            commission_earned=float(commission_earned or 0),
            success_rate=success_rate,
            avg_processing_time=_format_seconds(avg_processing_seconds) if avg_processing_seconds else None
        ))

    site_stat_rows = []
    for site, deposits, withdrawals, commission_paid in site_stats:
        site_stat_rows.append(SimpleNamespace(
            site_name=site.site_name,
            client_name=site.client.company_name if site.client else 'Unknown',
            total_deposits=float(deposits or 0),
            total_withdrawals=float(withdrawals or 0),
            commission_paid=float(commission_paid or 0),
            is_active=site.is_active
        ))

    return render_template(
        'admin/bank_gateway/reports.html',
        total_deposits=float(total_deposits or 0),
        total_withdrawals=float(total_withdrawals or 0),
        total_commissions=float(total_commissions or 0),
        net_revenue=net_revenue,
        deposit_count=deposit_count,
        withdrawal_count=withdrawal_count,
        commission_count=commission_count,
        provider_stats=provider_stat_rows,
        site_stats=site_stat_rows,
        daily_labels=daily_labels,
        daily_volumes=daily_volumes,
        completed_count=completed_count,
        pending_count=pending_count,
        rejected_count=rejected_count,
        clients=clients
    )


# --- Provider Commission Management ---
@admin_bp.route('/bank-gateway/provider-commissions')
@login_required
@superadmin_required
def provider_commissions():
    """List all provider commissions with filters"""
    # Get filter parameters
    status_filter = request.args.get('status', 'all')  # all, paid, unpaid
    provider_id = request.args.get('provider_id', type=int)
    transaction_type = request.args.get('type', '')  # deposit, withdraw
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query
    query = BankGatewayProviderCommission.query
    
    # Apply filters
    if status_filter == 'paid':
        query = query.filter_by(is_paid=True)
    elif status_filter == 'unpaid':
        query = query.filter_by(is_paid=False)
    
    if provider_id:
        query = query.filter_by(provider_id=provider_id)
    
    if transaction_type:
        query = query.filter_by(transaction_type=transaction_type)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(BankGatewayProviderCommission.created_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            # Add one day to include the entire day
            date_to_obj = date_to_obj + timedelta(days=1)
            query = query.filter(BankGatewayProviderCommission.created_at < date_to_obj)
        except ValueError:
            pass
    
    # Order by created date (newest first)
    query = query.order_by(BankGatewayProviderCommission.created_at.desc())
    
    # Paginate
    commissions_paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Calculate statistics
    total_commissions = BankGatewayProviderCommission.query.count()
    unpaid_count = BankGatewayProviderCommission.query.filter_by(is_paid=False).count()
    paid_count = BankGatewayProviderCommission.query.filter_by(is_paid=True).count()
    
    # Total amounts
    total_earned = db.session.query(
        db.func.sum(BankGatewayProviderCommission.amount)
    ).scalar() or 0
    
    total_paid = db.session.query(
        db.func.sum(BankGatewayProviderCommission.amount)
    ).filter_by(is_paid=True).scalar() or 0
    
    total_unpaid = db.session.query(
        db.func.sum(BankGatewayProviderCommission.amount)
    ).filter_by(is_paid=False).scalar() or 0
    
    # Get all providers for filter dropdown
    providers = BankGatewayProvider.query.all()
    
    stats = {
        'total_commissions': total_commissions,
        'unpaid_count': unpaid_count,
        'paid_count': paid_count,
        'total_earned': total_earned,
        'total_paid': total_paid,
        'total_unpaid': total_unpaid
    }
    
    return render_template('admin/bank_gateway/provider_commissions.html',
                         commissions=commissions_paginated,
                         providers=providers,
                         stats=stats,
                         status_filter=status_filter,
                         selected_provider_id=provider_id,
                         selected_type=transaction_type,
                         date_from=date_from,
                         date_to=date_to)


@admin_bp.route('/bank-gateway/provider-commission/<int:commission_id>/mark-paid', methods=['POST'])
@login_required
@superadmin_required
def mark_provider_commission_paid(commission_id):
    """Mark a provider commission as paid"""
    commission = BankGatewayProviderCommission.query.get_or_404(commission_id)
    
    if commission.is_paid:
        flash('This commission has already been marked as paid.', 'warning')
        return redirect(url_for('admin.provider_commissions'))
    
    # Get form data
    payment_method = request.form.get('payment_method', 'bank_transfer')
    payment_reference = request.form.get('payment_reference', '')
    payment_notes = request.form.get('payment_notes', '')
    
    # Update commission
    commission.is_paid = True
    commission.paid_at = now_eest()
    commission.paid_by = current_user.id
    commission.payment_method = payment_method
    commission.payment_reference = payment_reference or f'PAY-{uuid.uuid4().hex[:8].upper()}'
    commission.payment_notes = payment_notes
    
    db.session.commit()
    
    flash(f'Commission #{commission.id} marked as paid successfully! Reference: {commission.payment_reference}', 'success')
    return redirect(url_for('admin.provider_commissions'))


@admin_bp.route('/bank-gateway/provider/<int:provider_id>/commission-report')
@login_required
@superadmin_required
def provider_commission_report(provider_id):
    """Detailed commission report for a specific provider"""
    provider = BankGatewayProvider.query.get_or_404(provider_id)
    
    # Get date range from query params (default to last 30 days)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    
    if not date_from:
        date_from_obj = now_eest() - timedelta(days=30)
    else:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
        except ValueError:
            date_from_obj = now_eest() - timedelta(days=30)
    
    if not date_to:
        date_to_obj = now_eest()
    else:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
        except ValueError:
            date_to_obj = now_eest()
    
    # Query commissions for this provider
    commissions_query = BankGatewayProviderCommission.query.filter_by(
        provider_id=provider_id
    ).filter(
        BankGatewayProviderCommission.created_at >= date_from_obj,
        BankGatewayProviderCommission.created_at < date_to_obj
    )
    
    # Calculate statistics
    total_earned = db.session.query(
        db.func.sum(BankGatewayProviderCommission.amount)
    ).filter(
        BankGatewayProviderCommission.provider_id == provider_id,
        BankGatewayProviderCommission.created_at >= date_from_obj,
        BankGatewayProviderCommission.created_at < date_to_obj
    ).scalar() or 0
    
    total_paid = db.session.query(
        db.func.sum(BankGatewayProviderCommission.amount)
    ).filter(
        BankGatewayProviderCommission.provider_id == provider_id,
        BankGatewayProviderCommission.is_paid == True,
        BankGatewayProviderCommission.created_at >= date_from_obj,
        BankGatewayProviderCommission.created_at < date_to_obj
    ).scalar() or 0
    
    total_unpaid = total_earned - total_paid
    
    # Breakdown by transaction type
    deposit_commissions = db.session.query(
        db.func.sum(BankGatewayProviderCommission.amount)
    ).filter(
        BankGatewayProviderCommission.provider_id == provider_id,
        BankGatewayProviderCommission.transaction_type == 'deposit',
        BankGatewayProviderCommission.created_at >= date_from_obj,
        BankGatewayProviderCommission.created_at < date_to_obj
    ).scalar() or 0
    
    withdraw_commissions = db.session.query(
        db.func.sum(BankGatewayProviderCommission.amount)
    ).filter(
        BankGatewayProviderCommission.provider_id == provider_id,
        BankGatewayProviderCommission.transaction_type == 'withdraw',
        BankGatewayProviderCommission.created_at >= date_from_obj,
        BankGatewayProviderCommission.created_at < date_to_obj
    ).scalar() or 0
    
    # Get all commissions for detailed view
    commissions = commissions_query.order_by(
        BankGatewayProviderCommission.created_at.desc()
    ).all()
    
    stats = {
        'total_earned': total_earned,
        'total_paid': total_paid,
        'total_unpaid': total_unpaid,
        'deposit_commissions': deposit_commissions,
        'withdraw_commissions': withdraw_commissions,
        'commission_count': len(commissions),
        'paid_count': sum(1 for c in commissions if c.is_paid),
        'unpaid_count': sum(1 for c in commissions if not c.is_paid)
    }
    
    return render_template('admin/bank_gateway/provider_commission_report.html',
                         provider=provider,
                         commissions=commissions,
                         stats=stats,
                         date_from=date_from_obj.strftime('%Y-%m-%d'),
                         date_to=date_to_obj.strftime('%Y-%m-%d'))


# --- Withdrawal Request Management ---
@admin_bp.route('/bank-gateway/withdrawal-requests')
@login_required
@superadmin_required
def withdrawal_requests():
    """List all withdrawal requests with filters"""
    # Get filter parameters
    status_filter = request.args.get('status', 'pending')  # all, pending, approved, rejected, processing, completed
    client_id = request.args.get('client_id', type=int)
    provider_id = request.args.get('provider_id', type=int)
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '')  # Search by name, IBAN, reference
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    # Build query
    query = BankGatewayWithdrawalRequest.query
    
    # Apply filters
    if status_filter and status_filter != 'all':
        query = query.filter_by(status=status_filter)
    
    if client_id:
        # Filter by client's sites
        client_sites = BankGatewayClientSite.query.filter_by(client_id=client_id).all()
        site_ids = [s.id for s in client_sites]
        if site_ids:
            query = query.filter(BankGatewayWithdrawalRequest.client_site_id.in_(site_ids))
    
    if provider_id:
        query = query.filter_by(provider_id=provider_id)
    
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            db.or_(
                BankGatewayWithdrawalRequest.user_name.ilike(search_term),
                BankGatewayWithdrawalRequest.user_surname.ilike(search_term),
                BankGatewayWithdrawalRequest.iban.ilike(search_term),
                BankGatewayWithdrawalRequest.reference_code.ilike(search_term)
            )
        )
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            query = query.filter(BankGatewayWithdrawalRequest.created_at >= date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(BankGatewayWithdrawalRequest.created_at < date_to_obj)
        except ValueError:
            pass
    
    # Order by created date (newest first)
    query = query.order_by(BankGatewayWithdrawalRequest.created_at.desc())
    
    # Paginate
    withdrawals_paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Calculate statistics
    total_requests = BankGatewayWithdrawalRequest.query.count()
    pending_count = BankGatewayWithdrawalRequest.query.filter_by(status='pending').count()
    approved_count = BankGatewayWithdrawalRequest.query.filter_by(status='approved').count()
    rejected_count = BankGatewayWithdrawalRequest.query.filter_by(status='rejected').count()
    completed_count = BankGatewayWithdrawalRequest.query.filter_by(status='completed').count()
    
    # Total amounts
    total_amount = db.session.query(
        db.func.sum(BankGatewayWithdrawalRequest.amount)
    ).scalar() or 0
    
    pending_amount = db.session.query(
        db.func.sum(BankGatewayWithdrawalRequest.amount)
    ).filter_by(status='pending').scalar() or 0
    
    # Get clients and providers for filter dropdowns
    clients = Client.query.all()
    providers = BankGatewayProvider.query.all()
    
    stats = {
        'total_requests': total_requests,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'completed_count': completed_count,
        'total_amount': total_amount,
        'pending_amount': pending_amount
    }
    
    return render_template('admin/bank_gateway/withdrawal_requests.html',
                         withdrawals=withdrawals_paginated,
                         clients=clients,
                         providers=providers,
                         stats=stats,
                         status_filter=status_filter,
                         selected_client_id=client_id,
                         selected_provider_id=provider_id,
                         date_from=date_from,
                         date_to=date_to,
                         search=search)


@admin_bp.route('/bank-gateway/withdrawal-request/<int:request_id>')
@login_required
@superadmin_required
def withdrawal_request_detail(request_id):
    """View detailed information about a withdrawal request"""
    withdrawal = BankGatewayWithdrawalRequest.query.get_or_404(request_id)
    providers = BankGatewayProvider.query.filter_by(is_blocked=False).all()
    
    return render_template('admin/bank_gateway/withdrawal_detail.html',
                         withdrawal=withdrawal,
                         providers=providers)


@admin_bp.route('/bank-gateway/withdrawal-request/<int:request_id>/approve', methods=['POST'])
@login_required
@superadmin_required
def approve_withdrawal_request(request_id):
    """Approve a withdrawal request"""
    withdrawal = BankGatewayWithdrawalRequest.query.get_or_404(request_id)
    
    if withdrawal.status != 'pending':
        flash(f'Cannot approve withdrawal. Current status: {withdrawal.status}', 'warning')
        return redirect(url_for('admin.withdrawal_request_detail', request_id=request_id))
    
    # Get form data
    provider_id = request.form.get('provider_id', type=int)
    processing_notes = request.form.get('processing_notes', '')
    
    # Validate provider
    if provider_id:
        provider = BankGatewayProvider.query.get(provider_id)
        if not provider or provider.is_blocked:
            flash('Invalid or blocked provider selected', 'danger')
            return redirect(url_for('admin.withdrawal_request_detail', request_id=request_id))
        withdrawal.provider_id = provider_id
    
    # Update withdrawal
    withdrawal.status = 'approved'
    withdrawal.processed_at = now_eest()
    withdrawal.processed_by = current_user.id
    withdrawal.processing_notes = processing_notes
    
    # Create provider commission record if provider assigned
    if provider_id and withdrawal.provider_commission > 0:
        commission = BankGatewayProviderCommission(
            provider_id=provider_id,
            transaction_id=withdrawal.id,
            transaction_type='withdraw',
            amount=withdrawal.provider_commission,
            currency=withdrawal.currency,
            is_paid=False,
            related_transaction_ref=withdrawal.reference_code,
            notes=f'Commission for withdrawal {withdrawal.reference_code}'
        )
        db.session.add(commission)
    
    db.session.commit()
    
    flash(f'Withdrawal request {withdrawal.reference_code} approved successfully!', 'success')
    return redirect(url_for('admin.withdrawal_requests'))


@admin_bp.route('/bank-gateway/withdrawal-request/<int:request_id>/reject', methods=['POST'])
@login_required
@superadmin_required
def reject_withdrawal_request(request_id):
    """Reject a withdrawal request"""
    withdrawal = BankGatewayWithdrawalRequest.query.get_or_404(request_id)
    
    if withdrawal.status != 'pending':
        flash(f'Cannot reject withdrawal. Current status: {withdrawal.status}', 'warning')
        return redirect(url_for('admin.withdrawal_request_detail', request_id=request_id))
    
    # Get form data
    rejection_reason = request.form.get('rejection_reason', '')
    
    if not rejection_reason:
        flash('Rejection reason is required', 'danger')
        return redirect(url_for('admin.withdrawal_request_detail', request_id=request_id))
    
    # Update withdrawal
    withdrawal.status = 'rejected'
    withdrawal.processed_at = now_eest()
    withdrawal.processed_by = current_user.id
    withdrawal.rejection_reason = rejection_reason
    withdrawal.processing_notes = request.form.get('processing_notes', '')
    
    db.session.commit()
    
    flash(f'Withdrawal request {withdrawal.reference_code} rejected.', 'info')
    return redirect(url_for('admin.withdrawal_requests'))


# --- Admin Notifications ---
@admin_bp.route("/notifications")
@login_required
@superadmin_required
def notifications():
    """View all admin notifications"""
    from app.models.notification import AdminNotification
    
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')  # all, unread, read
    
    query = AdminNotification.query
    
    # Filter by status
    if status == 'unread':
        query = query.filter_by(is_read=False)
    elif status == 'read':
        query = query.filter_by(is_read=True)
    
    # Filter notifications for this admin or global notifications
    query = query.filter((AdminNotification.admin_id == current_user.id) | (AdminNotification.admin_id.is_(None)))
    
    # Order by creation date, urgent first
    notifications = query.order_by(AdminNotification.is_urgent.desc(), AdminNotification.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/notifications.html', 
                         notifications=notifications,
                         status=status)


@admin_bp.route("/notifications/<int:notification_id>/read", methods=['POST'])
@login_required
@superadmin_required
def mark_notification_read(notification_id):
    """Mark a specific notification as read"""
    from app.models.notification import AdminNotification
    
    success = AdminNotification.mark_as_read(notification_id, current_user.id)
    
    if success:
        flash("Notification marked as read", "success")
    else:
        flash("Notification not found or access denied", "error")
    
    return redirect(url_for('admin.notifications'))


@admin_bp.route("/notifications/mark-all-read", methods=['POST'])
@login_required
@superadmin_required
def mark_all_notifications_read():
    """Mark all notifications as read for current admin"""
    from app.models.notification import AdminNotification
    
    count = AdminNotification.mark_all_as_read(current_user.id)
    
    if count > 0:
        flash(f"Marked {count} notifications as read", "success")
    else:
        flash("No unread notifications found", "info")
    
    return redirect(url_for('admin.notifications'))


@admin_bp.route("/notifications/count")
@login_required
@superadmin_required
def get_notification_count():
    """Get unread notification count for current admin (AJAX endpoint)"""
    from app.models.notification import AdminNotification
    
    count = AdminNotification.get_unread_count(current_user.id)
    
    return jsonify({'count': count})


@admin_bp.route("/notifications/recent")
@login_required
@superadmin_required
def get_recent_notifications():
    """Get recent notifications for current admin (AJAX endpoint)"""
    from app.models.notification import AdminNotification
    
    notifications = AdminNotification.get_recent_notifications(current_user.id, limit=5)
    
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            'id': notification.id,
            'type': notification.notification_type.value,
            'title': notification.title,
            'message': notification.message,
            'is_urgent': notification.is_urgent,
            'is_read': notification.is_read,
            'created_at': notification.created_at.isoformat() if notification.created_at else None,
            'related_model': notification.related_model,
            'related_id': notification.related_id
        })
    
    return jsonify({'notifications': notifications_data})


# --- Create Payment ---
@admin_bp.route('/payments/create', methods=['GET', 'POST'])
@login_required
@superadmin_required
def create_payment():
    """Create a new payment"""
    print("[DEBUG] create_payment route called")
    from app.forms import PaymentForm
    from app.models import Client, Payment
    from app.models.enums import PaymentStatus
    
    form = PaymentForm()
    print(f"[DEBUG] Form created: {form}")
    
    # Populate client choices
    clients = Client.query.filter_by(is_active=True).all()
    form.client_id.choices = [(client.id, f"{client.company_name} ({client.username})") for client in clients]
    print(f"[DEBUG] Client choices populated: {len(form.client_id.choices)} clients")
    
    if form.validate_on_submit():
        try:
            transaction_id = (form.transaction_id.data or '').strip() or None

            payment = Payment(
                client_id=form.client_id.data,
                fiat_amount=form.fiat_amount.data,
                fiat_currency=form.fiat_currency.data,
                status=form.status.data,
                payment_method=form.payment_method.data,
                transaction_id=transaction_id,
                description=form.description.data
            )

            db.session.add(payment)
            db.session.commit()

            flash('Payment created successfully!', 'success')
            print(f"[DEBUG] Payment created with ID: {payment.id}")
            return redirect(url_for('admin.payments_list'))

        except Exception as e:
            db.session.rollback()
            flash(f'Error creating payment: {str(e)}', 'error')
            print(f"[ERROR] Failed to create payment: {str(e)}")
    
    print(f"[DEBUG] Rendering template with form: {form}")
    return render_template('admin/payments/create.html', form=form)

# View Payment route
@admin_bp.route('/payments/<int:payment_id>')
@login_required
@superadmin_required
def view_payment(payment_id):
    """View payment details"""
    from app.models import Payment
    
    payment = Payment.query.get_or_404(payment_id)
    
    return render_template('admin/payments/view.html', payment=payment)

# Update Payment Status route
@admin_bp.route('/payments/<int:payment_id>/status/<status>', methods=['POST'])
@login_required
@superadmin_required
def mark_payment_status(payment_id, status):
    """Update payment status"""
    from app.models import Payment
    from app.models.enums import PaymentStatus
    
    payment = Payment.query.get_or_404(payment_id)
    
    try:
        # Validate and set status
        payment.status = PaymentStatus(status)
        db.session.commit()
        
        flash(f'Payment status updated to {status}!', 'success')
    except ValueError:
        flash(f'Invalid status: {status}', 'error')
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating payment status: {str(e)}', 'error')
    
    return redirect(url_for('admin.view_payment', payment_id=payment_id))

# Edit Payment route
@admin_bp.route('/payments/<int:payment_id>/edit', methods=['GET', 'POST'])
@login_required
@superadmin_required
def edit_payment(payment_id):
    """Edit payment details"""
    from app.forms import PaymentForm
    from app.models import Payment, Client
    from app.models.enums import PaymentStatus
    
    payment = Payment.query.get_or_404(payment_id)
    form = PaymentForm(obj=payment)
    # Populate client choices
    clients = Client.query.filter_by(is_active=True).all()
    form.client_id.choices = [(client.id, f"{client.company_name} ({client.username})") for client in clients]
    if form.validate_on_submit():
        try:
            transaction_id = (form.transaction_id.data or '').strip() or None

            payment.client_id = form.client_id.data
            payment.fiat_amount = form.fiat_amount.data
            payment.fiat_currency = form.fiat_currency.data
            payment.status = form.status.data
            payment.payment_method = form.payment_method.data
            payment.transaction_id = transaction_id
            payment.description = form.description.data
            db.session.commit()
            flash('Payment updated successfully!', 'success')
            return redirect(url_for('admin.view_payment', payment_id=payment.id))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating payment: {str(e)}', 'error')
    return render_template('admin/payments/edit.html', form=form, payment=payment)

# Delete Payment route
@admin_bp.route('/payments/<int:payment_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_payment(payment_id):
    """Delete a payment"""
    from app.models import Payment
    
    payment = Payment.query.get_or_404(payment_id)
    
    try:
        db.session.delete(payment)
        db.session.commit()
        flash('Payment deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting payment: {str(e)}', 'error')
    
    return redirect(url_for('admin.payments_list'))

# --- Recurring Payments ---
@admin_bp.route('/recurring-payments')
@login_required
@superadmin_required
def recurring_payments():
    """Manage recurring payments"""
    recurring_payments = RecurringPayment.query.order_by(RecurringPayment.created_at.desc()).all()
    return render_template('admin/recurring_payments.html', recurring_payments=recurring_payments)


@admin_bp.route('/recurring-payments/new', methods=['GET', 'POST'])
@login_required
@superadmin_required
def new_recurring_payment():
    """Create a new recurring payment"""
    form = RecurringPaymentForm()
    _populate_recurring_payment_form_defaults(form)

    if form.validate_on_submit():
        try:
            recurring_payment = RecurringPayment(
                client_id=form.client_id.data,
                amount=float(form.amount.data),
                currency=form.currency.data,
                frequency=form.frequency.data,
                start_date=datetime.combine(form.start_date.data, datetime.min.time()),
                end_date=datetime.combine(form.end_date.data, datetime.min.time()) if form.end_date.data else None,
                description=form.description.data,
                payment_method=form.payment_method.data,
                payment_provider=form.payment_provider.data,
            )

            db.session.add(recurring_payment)
            db.session.commit()

            flash('Recurring payment created successfully.', 'success')
            return redirect(url_for('admin.recurring_payments'))

        except Exception as exc:
            current_app.logger.exception('Failed to create recurring payment')
            db.session.rollback()
            flash(f'Error creating recurring payment: {exc}', 'error')

    return render_template('admin/recurring_payment_form.html', form=form, recurring_payment=None)


@admin_bp.route('/recurring-payments/<int:recurring_payment_id>/edit', methods=['GET', 'POST'])
@login_required
@superadmin_required
def edit_recurring_payment(recurring_payment_id):
    """Edit an existing recurring payment"""
    recurring_payment = RecurringPayment.query.get_or_404(recurring_payment_id)
    form = RecurringPaymentForm(obj=recurring_payment)
    _populate_recurring_payment_form_defaults(form, editing=True)

    if request.method == 'GET':
        # Prefill date fields with date portion only
        if recurring_payment.start_date:
            form.start_date.data = recurring_payment.start_date.date()
        if recurring_payment.end_date:
            form.end_date.data = recurring_payment.end_date.date()
        if recurring_payment.status:
            form.status.data = recurring_payment.status

    if form.validate_on_submit():
        try:
            recurring_payment.client_id = form.client_id.data
            recurring_payment.amount = float(form.amount.data)
            recurring_payment.currency = form.currency.data
            recurring_payment.frequency = form.frequency.data
            recurring_payment.start_date = datetime.combine(form.start_date.data, datetime.min.time())
            recurring_payment.end_date = datetime.combine(form.end_date.data, datetime.min.time()) if form.end_date.data else None
            recurring_payment.description = form.description.data
            recurring_payment.payment_method = form.payment_method.data
            recurring_payment.payment_provider = form.payment_provider.data
            if form.status.data:
                recurring_payment.status = form.status.data

            db.session.commit()

            flash('Recurring payment updated successfully.', 'success')
            return redirect(url_for('admin.recurring_payments'))

        except Exception as exc:
            current_app.logger.exception('Failed to update recurring payment')
            db.session.rollback()
            flash(f'Error updating recurring payment: {exc}', 'error')

    return render_template('admin/recurring_payment_form.html', form=form, recurring_payment=recurring_payment)


@admin_bp.route('/recurring-payments/<int:recurring_payment_id>/toggle', methods=['POST'])
@login_required
@superadmin_required
def toggle_recurring_payment(recurring_payment_id):
    """Toggle recurring payment status between active and paused"""
    recurring_payment = RecurringPayment.query.get_or_404(recurring_payment_id)
    new_status = request.form.get('status')

    if new_status not in {'active', 'paused', 'cancelled'}:
        flash('Invalid status value provided.', 'error')
        return redirect(url_for('admin.recurring_payments'))

    try:
        recurring_payment.status = new_status
        db.session.commit()
        flash('Recurring payment status updated.', 'success')
    except Exception as exc:
        current_app.logger.exception('Failed to toggle recurring payment status')
        db.session.rollback()
        flash(f'Error updating status: {exc}', 'error')

    return redirect(url_for('admin.recurring_payments'))


@admin_bp.route('/recurring-payments/<int:recurring_payment_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_recurring_payment(recurring_payment_id):
    """Delete a recurring payment"""
    recurring_payment = RecurringPayment.query.get_or_404(recurring_payment_id)

    try:
        db.session.delete(recurring_payment)
        db.session.commit()
        flash('Recurring payment deleted successfully.', 'success')
    except Exception as exc:
        current_app.logger.exception('Failed to delete recurring payment')
        db.session.rollback()
        flash(f'Error deleting recurring payment: {exc}', 'error')

    return redirect(url_for('admin.recurring_payments'))


def _populate_recurring_payment_form_defaults(form: RecurringPaymentForm, editing: bool = False) -> None:
    """Populate recurring payment form choices and defaults."""
    clients = Client.query.filter_by(is_active=True).order_by(Client.company_name.asc()).all()
    form.client_id.choices = [(client.id, f"{client.company_name} ({client.email or client.username})") for client in clients]

    currency_choices = [('TRY', 'TRY'), ('USD', 'USD'), ('EUR', 'EUR')]
    if not form.currency.choices:
        form.currency.choices = currency_choices
    else:
        form.currency.choices = currency_choices

    frequency_choices = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('biweekly', 'Every 2 Weeks'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly')
    ]
    form.frequency.choices = frequency_choices

    method_choices = [
        ('bank_transfer', 'Bank Transfer'),
        ('crypto', 'Cryptocurrency'),
        ('card', 'Credit Card'),
    ]
    form.payment_method.choices = method_choices

    providers = BankGatewayProvider.query.order_by(BankGatewayProvider.name.asc()).all()
    provider_choices = [('', 'Select Provider')] + [(provider.id, provider.name) for provider in providers]
    form.payment_provider.choices = provider_choices

    status_choices = [
        ('active', 'Active'),
        ('paused', 'Paused'),
        ('cancelled', 'Cancelled'),
    ]
    form.status.choices = status_choices

    if not editing:
        form.status.data = 'active'


# --- Pricing Plans ---
@admin_bp.route('/pricing-plans')
@login_required
@superadmin_required
def pricing_plans():
    """Manage pricing plans"""
    from app.models.pricing_plan import PricingPlan, PlanType, BillingCycle
    
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    plan_type = request.args.get('plan_type')
    is_active = request.args.get('is_active')
    
    # Base query
    query = PricingPlan.query
    
    # Apply filters
    if plan_type:
        query = query.filter(PricingPlan.plan_type == plan_type)
    
    if is_active is not None:
        is_active_bool = is_active.lower() == 'true'
        query = query.filter(PricingPlan.is_active == is_active_bool)
    
    # Order by creation date (newest first)
    query = query.order_by(PricingPlan.created_at.desc())
    
    # Paginate results
    pricing_plans = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Calculate statistics
    total_plans = PricingPlan.query.count()
    active_plans = PricingPlan.query.filter_by(is_active=True).count()
    total_revenue = db.session.query(db.func.sum(PricingPlan.price)).filter(
        PricingPlan.is_active == True
    ).scalar() or 0
    
    stats = {
        'total_plans': total_plans,
        'active_plans': active_plans,
        'inactive_plans': total_plans - active_plans,
        'total_revenue': float(total_revenue)
    }
    
    return render_template('admin/pricing_plans.html',
                         pricing_plans=pricing_plans,
                         PlanType=PlanType,
                         BillingCycle=BillingCycle,
                         stats=stats)


# --- Commission Settings ---
@admin_bp.route('/commissions')
@login_required
@superadmin_required
def commissions():
    """Manage commission settings"""
    from app.models.commission_snapshot import CommissionSnapshot
    from app.models import Client
    from sqlalchemy import func, extract
    from datetime import datetime
    
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    client_id = request.args.get('client_id', type=int)
    month = request.args.get('month', type=int)
    year = request.args.get('year', type=int)
    
    # Default to current month/year if not specified
    if not month or not year:
        now = datetime.utcnow()
        month = month or now.month
        year = year or now.year
    
    # Base query with client join
    query = CommissionSnapshot.query.join(Client, CommissionSnapshot.client_id == Client.id)
    
    # Apply filters
    if client_id:
        query = query.filter(CommissionSnapshot.client_id == client_id)
    
    # Filter by month/year
    query = query.filter(
        extract('month', CommissionSnapshot.period_start) == month,
        extract('year', CommissionSnapshot.period_start) == year
    )
    
    # Order by period start (newest first)
    query = query.order_by(CommissionSnapshot.period_start.desc())
    
    # Paginate results
    commissions = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get all clients for filter dropdown
    clients = Client.query.filter_by(is_active=True).all()
    
    # Calculate statistics for the selected period
    period_commissions = CommissionSnapshot.query.filter(
        extract('month', CommissionSnapshot.period_start) == month,
        extract('year', CommissionSnapshot.period_start) == year
    )
    
    total_commission = db.session.query(func.sum(CommissionSnapshot.total_commission)).filter(
        extract('month', CommissionSnapshot.period_start) == month,
        extract('year', CommissionSnapshot.period_start) == year
    ).scalar() or 0
    
    avg_deposit_commission = db.session.query(func.avg(CommissionSnapshot.deposit_commission)).filter(
        extract('month', CommissionSnapshot.period_start) == month,
        extract('year', CommissionSnapshot.period_start) == year
    ).scalar() or 0
    
    avg_withdrawal_commission = db.session.query(func.avg(CommissionSnapshot.withdrawal_commission)).filter(
        extract('month', CommissionSnapshot.period_start) == month,
        extract('year', CommissionSnapshot.period_start) == year
    ).scalar() or 0
    
    stats = {
        'total_commission': float(total_commission),
        'avg_deposit_commission': float(avg_deposit_commission),
        'avg_withdrawal_commission': float(avg_withdrawal_commission),
        'total_snapshots': period_commissions.count(),
        'selected_month': month,
        'selected_year': year
    }
    
    return render_template('admin/commissions.html',
                         commissions=commissions,
                         clients=clients,
                         stats=stats)


# --- API Usage Logs ---
@admin_bp.route('/api-usage-logs')
@login_required
@superadmin_required
def api_usage_logs():
    """View API usage logs"""
    from app.models.api_usage import ApiUsage
    from app.models import Client
    from sqlalchemy import func, extract
    from datetime import datetime
    
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    client_id = request.args.get('client_id', type=int)
    endpoint = request.args.get('endpoint')
    method = request.args.get('method')
    status_code = request.args.get('status_code', type=int)
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    
    # Base query with client join
    query = ApiUsage.query.join(Client, ApiUsage.client_id == Client.id)
    
    # Apply filters
    if client_id:
        query = query.filter(ApiUsage.client_id == client_id)
    
    if endpoint:
        query = query.filter(ApiUsage.endpoint.contains(endpoint))
    
    if method:
        query = query.filter(ApiUsage.method == method)
    
    if status_code:
        query = query.filter(ApiUsage.status_code == status_code)
    
    if start_date:
        query = query.filter(ApiUsage.timestamp >= start_date)
    
    if end_date:
        # Add one day to include the end date fully
        end_date_obj = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
        query = query.filter(ApiUsage.timestamp < end_date_obj)
    
    # Order by timestamp (newest first)
    query = query.order_by(ApiUsage.timestamp.desc())
    
    # Paginate results
    api_logs = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Get all clients for filter dropdown
    clients = Client.query.filter_by(is_active=True).all()
    
    # Calculate statistics
    total_requests = query.count()
    
    # Response time statistics
    avg_response_time = db.session.query(func.avg(ApiUsage.response_time)).filter(
        ApiUsage.id.in_([log.id for log in query.all()])
    ).scalar() or 0
    
    # Status code distribution
    status_2xx = query.filter(ApiUsage.status_code.between(200, 299)).count()
    status_4xx = query.filter(ApiUsage.status_code.between(400, 499)).count()
    status_5xx = query.filter(ApiUsage.status_code.between(500, 599)).count()
    
    # Success rate
    success_rate = (status_2xx / total_requests * 100) if total_requests > 0 else 0
    
    # Top endpoints
    top_endpoints = db.session.query(
        ApiUsage.endpoint,
        func.count(ApiUsage.id).label('count')
    ).filter(
        ApiUsage.id.in_([log.id for log in query.all()])
    ).group_by(ApiUsage.endpoint).order_by(func.count(ApiUsage.id).desc()).limit(10).all()
    
    stats = {
        'total_requests': total_requests,
        'avg_response_time': float(avg_response_time),
        'status_2xx': status_2xx,
        'status_4xx': status_4xx,
        'status_5xx': status_5xx,
        'success_rate': success_rate,
        'top_endpoints': top_endpoints
    }
    
    return render_template('admin/api_usage_logs.html',
                         api_logs=api_logs,
                         clients=clients,
                         stats=stats)


# --- Database Management ---
@admin_bp.route('/database-management')
@login_required
@superadmin_required
def database_management():
    """Database management tools"""
    from sqlalchemy import text
    import os
    
    # Get database information
    db_info = {}
    
    try:
        # Get table information
        result = db.session.execute(text("""
            SELECT table_name, table_rows 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
            ORDER BY table_name
        """))
        tables = result.fetchall()
        
        # Get database size
        result = db.session.execute(text("""
            SELECT 
                ROUND(SUM(data_length + index_length) / 1024 / 1024, 2) as size_mb
            FROM information_schema.tables 
            WHERE table_schema = DATABASE()
        """))
        db_size = result.scalar() or 0
        
        # Get connection count (approximate)
        result = db.session.execute(text("SHOW PROCESSLIST"))
        connections = len(result.fetchall())
        
        db_info = {
            'tables': tables,
            'db_size': db_size,
            'connections': connections,
            'db_name': os.getenv('DATABASE_URL', 'sqlite:///instance/paycrypt_dev.db').split('/')[-1]
        }
        
    except Exception as e:
        db_info = {
            'error': str(e),
            'tables': [],
            'db_size': 0,
            'connections': 0,
            'db_name': 'Unknown'
        }
    
    # Recent database operations (from audit trail)
    from app.models.audit import AuditTrail
    recent_operations = AuditTrail.query.filter(
        AuditTrail.action_type.in_(['CREATE', 'UPDATE', 'DELETE'])
    ).order_by(AuditTrail.created_at.desc()).limit(10).all()
    
    return render_template('admin/database_management.html',
                         db_info=db_info,
                         recent_operations=recent_operations)


# --- Backup & Restore ---
@admin_bp.route('/backup-restore')
@login_required
@superadmin_required
def backup_restore():
    """Backup and restore functionality"""
    import os
    from datetime import datetime, timedelta
    
    # Get backup information
    backup_dir = os.path.join(os.getcwd(), 'backups')
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)
    
    # List existing backups
    backups = []
    if os.path.exists(backup_dir):
        for file in os.listdir(backup_dir):
            if file.endswith('.sql') or file.endswith('.db'):
                file_path = os.path.join(backup_dir, file)
                stat = os.stat(file_path)
                backups.append({
                    'filename': file,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_mtime),
                    'path': file_path
                })
    
    # Sort backups by creation date (newest first)
    backups.sort(key=lambda x: x['created'], reverse=True)
    
    # Get database statistics
    db_stats = {}
    try:
        # Get table counts
        from app.models import Client, Payment, User
        db_stats = {
            'clients': Client.query.count(),
            'payments': Payment.query.count(),
            'users': User.query.count(),
            'total_records': Client.query.count() + Payment.query.count() + User.query.count()
        }
    except Exception as e:
        db_stats = {'error': str(e)}
    
    # Recent backup operations (from audit trail)
    from app.models.audit import AuditTrail
    recent_backups = AuditTrail.query.filter(
        AuditTrail.action_type == 'BACKUP'
    ).order_by(AuditTrail.created_at.desc()).limit(5).all()
    
    return render_template('admin/backup_restore.html',
                         backups=backups,
                         db_stats=db_stats,
                         recent_backups=recent_backups)


# --- API Key Management for Admins ---
@admin_bp.route('/api-keys')
@login_required
@superadmin_required
def api_keys_management():
    """View and manage all client API keys"""
    from app.models.api_key import ClientApiKey
    
    # Get filter parameters
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)
    client_id_filter = request.args.get('client_id', type=int)
    status_filter = request.args.get('status')
    search = request.args.get('search')
    
    # Base query with client relationship
    query = ClientApiKey.query.join(Client, ClientApiKey.client_id == Client.id)
    
    # Apply filters
    if client_id_filter:
        query = query.filter(ClientApiKey.client_id == client_id_filter)
    
    if status_filter == 'active':
        query = query.filter(ClientApiKey.is_active == True)
    elif status_filter == 'inactive':
        query = query.filter(ClientApiKey.is_active == False)
    elif status_filter == 'expired':
        query = query.filter(ClientApiKey.expires_at < now_eest())
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                ClientApiKey.name.ilike(search_term),
                Client.company_name.ilike(search_term),
                ClientApiKey.key_prefix.ilike(search_term)
            )
        )
    
    # Order by most recent first
    query = query.order_by(ClientApiKey.created_at.desc())
    
    # Paginate results
    api_keys = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    # Calculate statistics
    total_keys = ClientApiKey.query.count()
    active_keys = ClientApiKey.query.filter_by(is_active=True).count()
    expired_keys = ClientApiKey.query.filter(ClientApiKey.expires_at < now_eest()).count()
    
    # Get top clients by API key count
    from sqlalchemy import func
    top_clients = db.session.query(
        Client.id,
        Client.company_name,
        func.count(ClientApiKey.id).label('key_count')
    ).join(ClientApiKey).group_by(Client.id, Client.company_name)\
     .order_by(func.count(ClientApiKey.id).desc()).limit(5).all()
    
    stats = {
        'total_keys': total_keys,
        'active_keys': active_keys,
        'inactive_keys': total_keys - active_keys,
        'expired_keys': expired_keys,
        'top_clients': top_clients
    }
    
    # Get all clients for filter dropdown
    clients = Client.query.order_by(Client.company_name).all()
    
    return render_template('admin/api_keys_management.html',
                         api_keys=api_keys,
                         clients=clients,
                         stats=stats,
                         client_id_filter=client_id_filter,
                         status_filter=status_filter,
                         search=search,
                         per_page=per_page)


@admin_bp.route('/api-keys/client/<int:client_id>')
@login_required
@superadmin_required
def client_api_keys(client_id):
    """View API keys for a specific client"""
    from app.models.api_key import ClientApiKey
    
    client = Client.query.get_or_404(client_id)
    api_keys = ClientApiKey.query.filter_by(client_id=client_id)\
                                  .order_by(ClientApiKey.created_at.desc()).all()
    
    # Calculate usage statistics
    total_usage = sum(key.usage_count for key in api_keys)
    active_keys = sum(1 for key in api_keys if key.is_active)
    
    stats = {
        'total_keys': len(api_keys),
        'active_keys': active_keys,
        'total_usage': total_usage,
        'last_used': max((key.last_used_at for key in api_keys if key.last_used_at), default=None)
    }
    
    return render_template('admin/client_api_keys_detail.html',
                         client=client,
                         api_keys=api_keys,
                         stats=stats)


@admin_bp.route('/api-keys/create/<int:client_id>', methods=['GET', 'POST'])
@login_required
@superadmin_required
def create_client_api_key(client_id):
    """Create a new API key for a client"""
    from app.models.api_key import ClientApiKey
    
    client = Client.query.get_or_404(client_id)
    
    if request.method == 'POST':
        try:
            name = request.form.get('name', 'Admin Created API Key')
            rate_limit = request.form.get('rate_limit', type=int) or 60
            expires_days = request.form.get('expires_days', type=int)
            permissions = request.form.getlist('permissions')
            
            # Create API key using the admin method
            api_key = ClientApiKey.create_for_admin(
                client_id=client_id,
                name=name,
                permissions=permissions,
                rate_limit=rate_limit,
                expires_days=expires_days,
                created_by_admin_id=current_user.id if hasattr(current_user, 'id') else None
            )
            
            # Store the keys temporarily in session for one-time display
            from flask import session
            session['new_api_key'] = api_key.key
            session['new_secret_key'] = api_key.secret_key
            session['new_webhook_secret'] = api_key.webhook_secret
            
            flash(_("API key created successfully. Save the credentials now - they won't be shown again!"), "success")
            return redirect(url_for('admin.view_api_key_credentials', key_id=api_key.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error creating API key: {str(e)}", "error")
    
    # Get available permissions based on client type
    available_permissions = ClientApiKey.get_permissions_for_client_type(
        'flat_rate' if client.is_flat_rate() else 'commission'
    )
    
    return render_template('admin/create_client_api_key.html',
                         client=client,
                         available_permissions=available_permissions)


@admin_bp.route('/api-keys/<int:key_id>')
@login_required
@superadmin_required
def view_api_key(key_id):
    """View API key details"""
    from app.models.api_key import ClientApiKey
    
    api_key = ClientApiKey.query.get_or_404(key_id)
    
    # Get usage logs
    from app.models.api_key import ApiKeyUsageLog
    recent_usage = ApiKeyUsageLog.query.filter_by(api_key_id=key_id)\
                                       .order_by(ApiKeyUsageLog.created_at.desc())\
                                       .limit(20).all()
    
    return render_template('admin/view_api_key.html',
                         api_key=api_key,
                         recent_usage=recent_usage)


@admin_bp.route('/api-keys/<int:key_id>/credentials')
@login_required
@superadmin_required
def view_api_key_credentials(key_id):
    """View API key credentials (one-time display after creation)"""
    from app.models.api_key import ClientApiKey
    from flask import session
    
    api_key = ClientApiKey.query.get_or_404(key_id)
    
    # Get credentials from session (only available right after creation)
    credentials = {
        'api_key': session.pop('new_api_key', None),
        'secret_key': session.pop('new_secret_key', None),
        'webhook_secret': session.pop('new_webhook_secret', None)
    }
    
    # If no credentials in session, don't show them (security)
    if not credentials['api_key']:
        flash("API key credentials are only shown once at creation. They cannot be retrieved later.", "warning")
    
    return render_template('admin/api_key_credentials.html',
                         api_key=api_key,
                         credentials=credentials)


@admin_bp.route('/api-keys/<int:key_id>/toggle-status', methods=['POST'])
@login_required
@superadmin_required
def toggle_api_key_status(key_id):
    """Toggle API key active/inactive status"""
    from app.models.api_key import ClientApiKey
    
    api_key = ClientApiKey.query.get_or_404(key_id)
    
    try:
        api_key.is_active = not api_key.is_active
        db.session.commit()
        
        status = "activated" if api_key.is_active else "deactivated"
        flash(_(f"API key '{api_key.name}' has been {status}"), "success")
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error updating API key status: {str(e)}", "error")
    
    return redirect(request.referrer or url_for('admin.api_keys_management'))


@admin_bp.route('/api-keys/<int:key_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_api_key(key_id):
    """Delete an API key"""
    from app.models.api_key import ClientApiKey
    
    api_key = ClientApiKey.query.get_or_404(key_id)
    
    try:
        key_name = api_key.name
        client_id = api_key.client_id
        
        db.session.delete(api_key)
        db.session.commit()
        
        flash(_(f"API key '{key_name}' has been deleted"), "success")
        return redirect(url_for('admin.client_api_keys', client_id=client_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting API key: {str(e)}", "error")
        return redirect(request.referrer or url_for('admin.api_keys_management'))


@admin_bp.route('/api-keys/<int:key_id>/regenerate', methods=['POST'])
@login_required
@superadmin_required
def regenerate_api_key(key_id):
    """Regenerate an API key (creates new credentials)"""
    from app.models.api_key import ClientApiKey
    from flask import session
    
    api_key = ClientApiKey.query.get_or_404(key_id)
    
    try:
        # Generate new keys
        new_key = ClientApiKey.generate_key()
        new_secret = secrets.token_hex(32)
        new_webhook_secret = secrets.token_hex(24)
        
        # Update the API key
        api_key.key = new_key
        api_key.key_prefix = new_key[:8] + '...'
        api_key.key_hash = ClientApiKey.hash_key(new_key)
        api_key.secret_key = new_secret
        api_key.webhook_secret = new_webhook_secret
        api_key.usage_count = 0
        api_key.last_used_at = None
        
        db.session.commit()
        
        # Store new credentials in session for one-time display
        session['new_api_key'] = new_key
        session['new_secret_key'] = new_secret
        session['new_webhook_secret'] = new_webhook_secret
        
        flash(_("API key regenerated successfully. Save the new credentials now!"), "success")
        return redirect(url_for('admin.view_api_key_credentials', key_id=key_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error regenerating API key: {str(e)}", "error")
        return redirect(request.referrer or url_for('admin.api_keys_management'))


