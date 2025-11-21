from datetime import timedelta

from flask import Blueprint, render_template, redirect, request, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func, or_

from app.models import Branch, Client
from app.models.admin import AdminUser
from app.models.api_key import ClientApiKey, ApiKeyUsageLog
from app.models.audit import AuditTrail, AuditLog
from app.models.bank_gateway import (
    BankGatewayProvider,
    BankGatewayAccount,
    BankGatewayClientSite,
    BankGatewayTransaction,
)
from app.models.login_history import LoginHistory
from app.forms import BranchForm  # We'll create this
from app import db
from app.utils.decorators import owner_required
from app.utils.timezone import now_eest
from flask_babel import _

owner_bp = Blueprint("owner", __name__, url_prefix="/owner")

# --- Owner Dashboard ---
@owner_bp.route("/dashboard")
@login_required
@owner_required
def owner_dashboard():
    branches = Branch.query.order_by(Branch.created_at.desc()).all()
    total_branches = len(branches)
    active_branches = len([b for b in branches if b.is_active])

    # Financial stats (read-only)
    total_transactions = sum(b.total_transactions or 0 for b in branches)
    total_volume = sum(float(b.total_volume or 0) for b in branches)

    admin_users = AdminUser.query.order_by(AdminUser.created_at.desc()).limit(8).all()
    total_admins = AdminUser.query.count()
    active_admins = AdminUser.query.filter_by(_active=True).count()
    superuser_admins = AdminUser.query.filter_by(is_superuser=True).count()

    total_clients = Client.query.count()
    active_clients = Client.query.filter_by(is_active=True).count()
    verified_clients = Client.query.filter_by(is_verified=True).count()
    recent_clients = Client.query.order_by(Client.created_at.desc()).limit(8).all()
    clients_with_keys = db.session.query(ClientApiKey.client_id).distinct().count()

    providers = BankGatewayProvider.query.all()
    provider_count = len(providers)
    active_providers = len([provider for provider in providers if not getattr(provider, "is_blocked", False)])
    account_count = BankGatewayAccount.query.count()
    client_sites = BankGatewayClientSite.query.count()
    pending_bank_transactions = BankGatewayTransaction.query.filter_by(status='pending').count()

    recent_audit_trail = AuditTrail.query.order_by(AuditTrail.created_at.desc()).limit(10).all()
    recent_branch_audit = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(10).all()

    recent_api_keys = ClientApiKey.query.order_by(ClientApiKey.created_at.desc()).limit(10).all()
    total_api_keys = ClientApiKey.query.count()

    recent_security_events = LoginHistory.query.order_by(LoginHistory.login_at.desc()).limit(10).all()
    failed_logins_last_24h = LoginHistory.query.filter(
        LoginHistory.success.is_(False),
        LoginHistory.login_at >= now_eest() - timedelta(days=1)
    ).count()
    active_security_users = len({event.username for event in recent_security_events if event.success})

    admin_stats = {
        'total': total_admins,
        'active': active_admins,
        'superusers': superuser_admins,
        'recent': admin_users,
    }

    client_stats = {
        'total': total_clients,
        'active': active_clients,
        'verified': verified_clients,
        'recent': recent_clients,
        'with_api_keys': clients_with_keys,
    }

    provider_stats = {
        'providers': provider_count,
        'active_providers': active_providers,
        'accounts': account_count,
        'client_sites': client_sites,
        'pending_transactions': pending_bank_transactions,
    }

    audit_stats = {
        'recent_audit_trail': recent_audit_trail,
        'recent_branch_audit': recent_branch_audit,
        'total_audit_trail': AuditTrail.query.count(),
        'total_branch_audit': AuditLog.query.count(),
    }

    api_stats = {
        'total_api_keys': total_api_keys,
        'recent_keys': recent_api_keys,
        'recent_usage': ApiKeyUsageLog.query.order_by(ApiKeyUsageLog.created_at.desc()).limit(10).all(),
    }

    security_stats = {
        'recent_events': recent_security_events,
        'failed_last_24h': failed_logins_last_24h,
        'suspicious': LoginHistory.get_suspicious_activity(),
        'active_users': active_security_users,
    }

    stats = {
        'total_branches': total_branches,
        'active_branches': active_branches,
        'total_transactions': total_transactions,
        'total_volume': total_volume,
    }

    return render_template(
        "owner/dashboard.html",
        branches=branches,
        stats=stats,
        admin_stats=admin_stats,
        client_stats=client_stats,
        provider_stats=provider_stats,
        audit_stats=audit_stats,
        api_stats=api_stats,
        security_stats=security_stats,
    )


@owner_bp.route("/admin-users")
@login_required
@owner_required
def admin_users():
    search = request.args.get("search", "").strip()
    query = AdminUser.query

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                AdminUser.username.ilike(like),
                AdminUser.email.ilike(like),
                AdminUser.first_name.ilike(like),
                AdminUser.last_name.ilike(like),
            )
        )

    admins = query.order_by(AdminUser.created_at.desc()).all()

    stats = {
        "total": len(admins),
        "active": len([a for a in admins if a.is_active]),
        "superusers": len([a for a in admins if a.is_superuser]),
    }

    return render_template(
        "owner/admin_users.html",
        admins=admins,
        stats=stats,
        search=search,
    )


@owner_bp.route("/clients")
@login_required
@owner_required
def owner_clients():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()

    query = Client.query

    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(
                Client.company_name.ilike(like),
                Client.email.ilike(like),
                Client.contact_email.ilike(like),
            )
        )

    if status == "active":
        query = query.filter(Client.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(Client.is_active.is_(False))

    clients = query.order_by(Client.created_at.desc()).all()

    stats = {
        "total": Client.query.count(),
        "active": Client.query.filter_by(is_active=True).count(),
        "verified": Client.query.filter_by(is_verified=True).count(),
        "with_api_keys": db.session.query(ClientApiKey.client_id).distinct().count(),
    }

    return render_template(
        "owner/clients.html",
        clients=clients,
        stats=stats,
        search=search,
        status=status,
    )

@owner_bp.route("/providers")
@owner_required
@login_required
def owner_providers():
    providers = (
        BankGatewayProvider.query
        .order_by(BankGatewayProvider.created_at.desc())
        .all()
    )

    stats = {
        "total_providers": len(providers),
        "active_providers": len([p for p in providers if not getattr(p, "is_blocked", False)]),
        "total_accounts": BankGatewayAccount.query.count(),
        "pending_transactions": BankGatewayTransaction.query.filter_by(status='pending').count(),
    }

    accounts_by_provider = (
        db.session.query(
            BankGatewayAccount.provider_id,
            func.count(BankGatewayAccount.id).label("account_count"),
        )
        .group_by(BankGatewayAccount.provider_id)
        .all()
    )

    account_map = {item.provider_id: item.account_count for item in accounts_by_provider}

    return render_template(
        "owner/providers.html",
        providers=providers,
        stats=stats,
        account_map=account_map,
    )


@owner_bp.route("/system-health")
@login_required
@owner_required
def system_health():
    cutoff = now_eest() - timedelta(days=1)
    total_logins_24h = LoginHistory.query.filter(
        LoginHistory.login_at >= cutoff
    ).count()

    failed_logins_24h = LoginHistory.query.filter(
        LoginHistory.success.is_(False),
        LoginHistory.login_at >= cutoff
    ).count()

    pending_transactions = BankGatewayTransaction.query.filter_by(status='pending').count()
    confirmed_transactions = BankGatewayTransaction.query.filter_by(status='confirmed').count()

    stats = {
        "logins_24h": total_logins_24h,
        "failed_logins_24h": failed_logins_24h,
        "pending_transactions": pending_transactions,
        "confirmed_transactions": confirmed_transactions,
        "active_branches": Branch.query.filter_by(is_active=True).count(),
    }

    recent_logins = LoginHistory.query.order_by(LoginHistory.login_at.desc()).limit(25).all()
    recent_transactions = BankGatewayTransaction.query.order_by(BankGatewayTransaction.created_at.desc()).limit(25).all()

    return render_template(
        "owner/system_health.html",
        stats=stats,
        recent_logins=recent_logins,
        recent_transactions=recent_transactions,
    )


@owner_bp.route("/audit-logs")
@login_required
@owner_required
def owner_audit_logs():
    audit_trail_entries = AuditTrail.query.order_by(AuditTrail.created_at.desc()).limit(100).all()
    branch_audit_entries = AuditLog.query.order_by(AuditLog.timestamp.desc()).limit(100).all()

    return render_template(
        "owner/audit_logs.html",
        audit_trail_entries=audit_trail_entries,
        branch_audit_entries=branch_audit_entries,
    )


@owner_bp.route("/api-management")
@login_required
@owner_required
def api_management():
    api_keys = ClientApiKey.query.order_by(ClientApiKey.created_at.desc()).all()
    usage_logs = ApiKeyUsageLog.query.order_by(ApiKeyUsageLog.created_at.desc()).limit(50).all()

    stats = {
        "total_keys": len(api_keys),
        "active_keys": len([key for key in api_keys if key.is_active]),
        "clients_with_keys": db.session.query(ClientApiKey.client_id).distinct().count(),
    }

    return render_template(
        "owner/api_management.html",
        api_keys=api_keys,
        usage_logs=usage_logs,
        stats=stats,
    )


@owner_bp.route("/security-center")
@login_required
@owner_required
def security_center():
    recent_events = LoginHistory.query.order_by(LoginHistory.login_at.desc()).limit(50).all()
    suspicious_activity = LoginHistory.get_suspicious_activity()

    stats = {
        "recent_events": len(recent_events),
        "active_users": len(set(event.username for event in recent_events if event.success)),
        "failed_events": len([event for event in recent_events if not event.success]),
    }

    return render_template(
        "owner/security_center.html",
        recent_events=recent_events,
        suspicious_activity=suspicious_activity,
        stats=stats,
    )


# --- Branch Management ---
@owner_bp.route("/branches")
@login_required
@owner_required
def list_branches():
    branches = Branch.query.all()
    return render_template("owner/branches.html", branches=branches)

@owner_bp.route("/branch/add", methods=["GET", "POST"])
@login_required
@owner_required
def add_branch():
    form = BranchForm()
    if form.validate_on_submit():
        from app.models import AdminUser

        # Create the superadmin user for this branch
        superadmin = AdminUser(
            username=form.superadmin_username.data,
            email=form.superadmin_email.data,
            password=form.superadmin_password.data,
            first_name=form.superadmin_first_name.data,
            last_name=form.superadmin_last_name.data,
            is_superuser=True  # This branch has superadmin access
        )
        db.session.add(superadmin)
        db.session.flush()  # Get the ID

        # Create the branch (linked to the superadmin)
        branch = Branch(
            name=form.name.data,
            address=form.address.data,
            city=form.city.data,
            country=form.country.data,
            postal_code=form.postal_code.data,
            phone=form.phone.data,
            email=form.email.data,
            client_id=None,  # Superadmin branches don't need clients
            webhook_url=form.webhook_url.data,
            is_active=form.is_active.data,
        )
        branch.adminuser_id = superadmin.id  # Set the relationship
        db.session.add(branch)
        db.session.commit()

        flash(f"Branch '{branch.name}' and superadmin account '{superadmin.username}' created successfully!", "success")
        return redirect(url_for("owner.list_branches"))
    return render_template("owner/branch_form.html", form=form, action="Add")

@owner_bp.route("/branch/<int:branch_id>/edit", methods=["GET", "POST"])
@login_required
@owner_required
def edit_branch(branch_id):
    branch = Branch.query.get_or_404(branch_id)

    # Get the associated superadmin
    superadmin = branch.adminuser if hasattr(branch, 'adminuser') and branch.adminuser else None

    if not superadmin:
        flash("Branch superadmin account not found.", "error")
        return redirect(url_for("owner.list_branches"))

    # Create form and populate with branch data
    form = BranchForm(obj=branch)

    # Populate superadmin fields
    if not form.superadmin_username.data:
        form.superadmin_username.data = superadmin.username
    if not form.superadmin_email.data:
        form.superadmin_email.data = superadmin.email
    if not form.superadmin_first_name.data:
        form.superadmin_first_name.data = superadmin.first_name
    if not form.superadmin_last_name.data:
        form.superadmin_last_name.data = superadmin.last_name

    if form.validate_on_submit():
        # Update branch data
        branch.name = form.name.data
        branch.address = form.address.data
        branch.city = form.city.data
        branch.country = form.country.data
        branch.postal_code = form.postal_code.data
        branch.phone = form.phone.data
        branch.email = form.email.data
        branch.webhook_url = form.webhook_url.data
        branch.is_active = form.is_active.data

        # Update superadmin data
        superadmin.username = form.superadmin_username.data
        superadmin.email = form.superadmin_email.data
        if form.superadmin_password.data:  # Only update password if provided
            superadmin.set_password(form.superadmin_password.data)
        superadmin.first_name = form.superadmin_first_name.data
        superadmin.last_name = form.superadmin_last_name.data

        db.session.commit()
        flash("Branch and superadmin account updated successfully.", "success")
        return redirect(url_for("owner.list_branches"))
    return render_template("owner/branch_form.html", form=form, action="Edit")

@owner_bp.route("/branch/<int:branch_id>/delete", methods=["POST"])
@login_required
@owner_required
def delete_branch(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    db.session.delete(branch)
    db.session.commit()
    flash("Branch deleted successfully.", "success")
    return redirect(url_for("owner.list_branches"))

# --- Branch API Management ---
@owner_bp.route("/branch/<int:branch_id>/api")
@login_required
@owner_required
def branch_api(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    return render_template("owner/branch_api.html", branch=branch)

@owner_bp.route("/branch/<int:branch_id>/api/regenerate", methods=["POST"])
@login_required
@owner_required
def regenerate_api_key(branch_id):
    branch = Branch.query.get_or_404(branch_id)
    import secrets
    branch.api_key = secrets.token_urlsafe(32)
    branch.api_secret = secrets.token_urlsafe(32)
    db.session.commit()
    flash("API credentials regenerated.", "success")
    return redirect(url_for("owner.branch_api", branch_id=branch_id))

# --- Financial Stats and Analytics ---
@owner_bp.route("/analytics")
@login_required
@owner_required
def analytics():
    branches = Branch.query.all()
    
    # Aggregate stats
    stats = {
        'total_branches': len(branches),
        'active_branches': len([b for b in branches if b.is_active]),
        'total_transactions': sum(b.total_transactions for b in branches),
        'total_volume': sum(float(b.total_volume) for b in branches),
    }
    
    # Per branch stats
    branch_stats = []
    for branch in branches:
        branch_stats.append({
            'name': branch.name,
            'transactions': branch.total_transactions,
            'volume': float(branch.total_volume),
            'is_active': branch.is_active,
        })
    
    return render_template("owner/analytics.html", stats=stats, branch_stats=branch_stats)