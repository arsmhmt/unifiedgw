from app.models.notification import AdminNotification, AdminNotificationType
from app.models import Payment, WithdrawalRequest, Client
from app import db
from flask import current_app


def create_payment_request_notification(payment):
    """Create admin notification for new payment request"""
    try:
        client = Client.query.get(payment.client_id)
        client_name = client.name if client else f"Client {payment.client_id}"

        title = f"New Payment Request - {payment.crypto_currency}"
        message = f"{client_name} has requested a payment of {payment.fiat_amount} {payment.fiat_currency} ({payment.crypto_amount} {payment.crypto_currency})."

        AdminNotification.create_notification(
            notification_type=AdminNotificationType.PAYMENT_REQUEST,
            title=title,
            message=message,
            related_id=payment.id,
            related_model='Payment',
            is_urgent=True  # Payment requests are urgent
        )

        current_app.logger.info(f"Admin notification created for payment {payment.id}")

    except Exception as e:
        current_app.logger.error(f"Failed to create payment notification: {str(e)}")


def create_withdrawal_request_notification(withdrawal_request):
    """Create admin notification for new withdrawal request"""
    try:
        client = Client.query.get(withdrawal_request.client_id)
        client_name = client.name if client else f"Client {withdrawal_request.client_id}"

        title = f"New Withdrawal Request - {withdrawal_request.currency}"
        message = f"{client_name} has requested a withdrawal of {withdrawal_request.amount} {withdrawal_request.currency}."

        AdminNotification.create_notification(
            notification_type=AdminNotificationType.WITHDRAWAL_REQUEST,
            title=title,
            message=message,
            related_id=withdrawal_request.id,
            related_model='WithdrawalRequest',
            is_urgent=True  # Withdrawal requests are urgent
        )

        current_app.logger.info(f"Admin notification created for withdrawal {withdrawal_request.id}")

    except Exception as e:
        current_app.logger.error(f"Failed to create withdrawal notification: {str(e)}")


def create_client_registration_notification(client):
    """Create admin notification for new client registration"""
    try:
        title = f"New Client Registration - {client.name}"
        message = f"A new client '{client.name}' has registered and requires approval."

        AdminNotification.create_notification(
            notification_type=AdminNotificationType.CLIENT_REGISTRATION,
            title=title,
            message=message,
            related_id=client.id,
            related_model='Client',
            is_urgent=False
        )

        current_app.logger.info(f"Admin notification created for client registration {client.id}")

    except Exception as e:
        current_app.logger.error(f"Failed to create client registration notification: {str(e)}")


def create_system_alert_notification(title, message, is_urgent=False):
    """Create admin notification for system alerts"""
    try:
        AdminNotification.create_notification(
            notification_type=AdminNotificationType.SYSTEM_ALERT,
            title=title,
            message=message,
            is_urgent=is_urgent
        )

        current_app.logger.info(f"Admin system alert notification created: {title}")

    except Exception as e:
        current_app.logger.error(f"Failed to create system alert notification: {str(e)}")


def create_security_alert_notification(title, message):
    """Create admin notification for security alerts"""
    try:
        AdminNotification.create_notification(
            notification_type=AdminNotificationType.SECURITY_ALERT,
            title=title,
            message=message,
            is_urgent=True  # Security alerts are always urgent
        )

        current_app.logger.info(f"Admin security alert notification created: {title}")

    except Exception as e:
        current_app.logger.error(f"Failed to create security alert notification: {str(e)}")