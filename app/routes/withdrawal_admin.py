from flask import Blueprint, render_template, request, url_for
from flask_login import login_required
from types import SimpleNamespace

from app.models import WithdrawalRequest, Client
from app.models.enums import WithdrawalType, WithdrawalStatus


withdrawal_admin = Blueprint('withdrawal_admin', __name__, url_prefix='/admin/withdrawals')


def _compute_withdrawal_stats(withdrawal_type=None):
    base_query = WithdrawalRequest.query
    if withdrawal_type is not None:
        base_query = base_query.filter(
            WithdrawalRequest.withdrawal_type == withdrawal_type
        )

    counts_by_status = {
        status.value: base_query.filter(WithdrawalRequest.status == status).count()
        for status in WithdrawalStatus
    }

    return {
        'total': base_query.count(),
        'pending': counts_by_status.get(WithdrawalStatus.PENDING.value, 0),
        'approved': counts_by_status.get(WithdrawalStatus.APPROVED.value, 0),
        'rejected': counts_by_status.get(WithdrawalStatus.REJECTED.value, 0),
        'completed': counts_by_status.get(WithdrawalStatus.COMPLETED.value, 0),
        'cancelled': counts_by_status.get(WithdrawalStatus.CANCELLED.value, 0),
        'processing': counts_by_status.get(WithdrawalStatus.PROCESSING.value, 0),
        'failed': counts_by_status.get(WithdrawalStatus.FAILED.value, 0),
        'by_status': counts_by_status,
    }


def _apply_filters(query, status_filter, client_filter):
    status_enum = None
    if status_filter:
        try:
            status_enum = WithdrawalStatus(status_filter)
        except ValueError:
            status_enum = None

    if status_enum:
        query = query.filter(WithdrawalRequest.status == status_enum)

    if client_filter:
        query = query.filter(WithdrawalRequest.client_id == client_filter)

    return query


def _get_clients():
    return Client.query.order_by(Client.company_name.asc()).all()


def _render_withdrawal_list(
    template_name,
    base_query,
    status_filter,
    client_filter,
    page,
    per_page,
    *,
    stats_scope=None,
    list_endpoint='withdrawal_admin.withdrawal_history',
    extra_params=None,
):
    query = _apply_filters(base_query, status_filter, client_filter)

    withdrawals = query.order_by(WithdrawalRequest.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    if isinstance(stats_scope, WithdrawalType):
        stats = _compute_withdrawal_stats(stats_scope)
    elif stats_scope == 'user':
        stats = _compute_withdrawal_stats(WithdrawalType.USER_REQUEST)
    elif stats_scope == 'client':
        stats = _compute_withdrawal_stats(WithdrawalType.CLIENT_BALANCE)
    else:
        stats = _compute_withdrawal_stats()

    status_counts = SimpleNamespace()
    setattr(status_counts, 'all', stats['total'])
    setattr(status_counts, 'pending', stats['pending'])
    setattr(status_counts, 'approved', stats['approved'])
    setattr(status_counts, 'completed', stats['completed'])
    setattr(status_counts, 'rejected', stats['rejected'])
    setattr(status_counts, 'cancelled', stats['cancelled'])

    base_params = extra_params.copy() if extra_params else {}

    if client_filter:
        base_params['client'] = client_filter
    else:
        base_params.pop('client', None)

    current_status = status_filter if status_filter not in (None, '', 'all') else 'all'
    if current_status != 'all':
        base_params['status'] = current_status
    else:
        base_params.pop('status', None)

    pagination_params = {k: v for k, v in base_params.items() if v not in (None, '')}

    status_tab_definitions = [
        ('all', 'All', 'secondary'),
        ('pending', 'Pending', 'warning'),
        ('approved', 'Approved', 'info'),
        ('completed', 'Completed', 'success'),
        ('rejected', 'Rejected', 'danger'),
        ('cancelled', 'Cancelled', 'secondary'),
    ]

    status_tabs = []
    for key, label, badge in status_tab_definitions:
        params = {k: v for k, v in base_params.items() if k != 'status'}
        if key != 'all':
            params['status'] = key
        url = url_for(list_endpoint, **{k: v for k, v in params.items() if v not in (None, '')})
        status_tabs.append(
            {
                'key': key,
                'label': label,
                'badge_class': badge,
                'count': getattr(status_counts, key, 0),
                'url': url,
                'active': key == current_status,
            }
        )

    return render_template(
        template_name,
        withdrawals=withdrawals,
        status_counts=status_counts,
        status=current_status,
        stats=stats,
        status_filter=current_status if current_status != 'all' else None,
        client_filter=client_filter,
        list_endpoint=list_endpoint,
        pagination_params=pagination_params,
        status_tabs=status_tabs,
    )


@withdrawal_admin.route('/client-requests')
@login_required
def client_withdrawal_requests():
    status_filter = request.args.get('status')
    client_filter = request.args.get('client', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    query = WithdrawalRequest.query.filter(
        WithdrawalRequest.withdrawal_type == WithdrawalType.CLIENT_BALANCE
    )
    query = _apply_filters(query, status_filter, client_filter)

    withdrawals = query.order_by(WithdrawalRequest.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    stats = _compute_withdrawal_stats(WithdrawalType.CLIENT_BALANCE)
    clients = _get_clients()

    return render_template(
        'admin/withdrawals/client_requests.html',
        stats=stats,
        clients=clients,
        withdrawals=withdrawals,
        status_filter=status_filter,
        client_filter=client_filter,
    )


@withdrawal_admin.route('/user-requests')
@login_required
def user_withdrawal_requests():
    status_filter = request.args.get('status')
    client_filter = request.args.get('client', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    query = WithdrawalRequest.query.filter(
        WithdrawalRequest.withdrawal_type == WithdrawalType.USER_REQUEST
    )
    query = _apply_filters(query, status_filter, client_filter)

    withdrawals = query.order_by(WithdrawalRequest.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    stats = _compute_withdrawal_stats(WithdrawalType.USER_REQUEST)
    clients = _get_clients()

    return render_template(
        'admin/withdrawals/user_requests.html',
        stats=stats,
        clients=clients,
        withdrawals=withdrawals,
        status_filter=status_filter,
        client_filter=client_filter,
    )


@withdrawal_admin.route('/user-bulk')
@login_required
def user_withdrawal_bulk():
    return render_template('admin/withdrawals/user_bulk.html')


@withdrawal_admin.route('/client-bulk')
@login_required
def client_withdrawal_bulk():
    return render_template('admin/withdrawals/client_bulk.html')


@withdrawal_admin.route('/history')
@login_required
def withdrawal_history():
    status_filter = request.args.get('status', 'all')
    client_filter = request.args.get('client', type=int)
    withdrawal_type_filter = request.args.get('type')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    base_query = WithdrawalRequest.query
    stats_scope = None
    if withdrawal_type_filter == 'user':
        base_query = base_query.filter(WithdrawalRequest.withdrawal_type == WithdrawalType.USER_REQUEST)
        stats_scope = WithdrawalType.USER_REQUEST
    elif withdrawal_type_filter == 'client':
        base_query = base_query.filter(WithdrawalRequest.withdrawal_type == WithdrawalType.CLIENT_BALANCE)
        stats_scope = WithdrawalType.CLIENT_BALANCE

    return _render_withdrawal_list(
        'admin/withdrawals/list.html',
        base_query,
        status_filter,
        client_filter,
        page,
        per_page,
        stats_scope=stats_scope,
        list_endpoint='withdrawal_admin.withdrawal_history',
        extra_params={'type': withdrawal_type_filter} if withdrawal_type_filter else None,
    )


@withdrawal_admin.route('/reports')
@login_required
def withdrawal_reports():
    status_filter = request.args.get('status', 'all')
    client_filter = request.args.get('client', type=int)
    withdrawal_type_filter = request.args.get('type')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    base_query = WithdrawalRequest.query
    stats_scope = None
    if withdrawal_type_filter == 'user':
        base_query = base_query.filter(WithdrawalRequest.withdrawal_type == WithdrawalType.USER_REQUEST)
        stats_scope = WithdrawalType.USER_REQUEST
    elif withdrawal_type_filter == 'client':
        base_query = base_query.filter(WithdrawalRequest.withdrawal_type == WithdrawalType.CLIENT_BALANCE)
        stats_scope = WithdrawalType.CLIENT_BALANCE

    return _render_withdrawal_list(
        'admin/withdrawals/list.html',
        base_query,
        status_filter,
        client_filter,
        page,
        per_page,
        stats_scope=stats_scope,
        list_endpoint='withdrawal_admin.withdrawal_reports',
        extra_params={'type': withdrawal_type_filter} if withdrawal_type_filter else None,
    )
