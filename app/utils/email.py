import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import current_app, url_for, render_template
from datetime import datetime, timedelta
from ..utils.timezone import now_eest
import secrets

def send_email(subject, recipient, template, **kwargs):
    """Send an email using the configured SMTP settings"""
    msg = MIMEMultipart()
    msg['From'] = current_app.config['MAIL_DEFAULT_SENDER']
    msg['To'] = recipient
    msg['Subject'] = subject
    
    # Render HTML template
    html = render_template(f'emails/{template}.html', **kwargs)
    msg.attach(MIMEText(html, 'html'))
    
    try:
        with smtplib.SMTP(
            current_app.config['MAIL_SERVER'], 
            current_app.config['MAIL_PORT']
        ) as server:
            if current_app.config['MAIL_USE_TLS']:
                server.starttls()
            if current_app.config['MAIL_USERNAME']:
                server.login(
                    current_app.config['MAIL_USERNAME'],
                    current_app.config['MAIL_PASSWORD']
                )
            server.send_message(msg)
        return True
    except Exception as e:
        current_app.logger.error(f'Failed to send email: {str(e)}')
        return False

def send_verification_email(user):
    """Send email verification link to user"""
    token = secrets.token_urlsafe(32)
    user.email_verification_token = token
    
    # Set expiration (24 hours from now)
    from app import db
    db.session.commit()
    
    verification_url = url_for(
        'auth.verify_email',
        token=token,
        _external=True
    )
    
    # Get username from user or associated client
    username = getattr(user, 'username', '')
    if not username and hasattr(user, 'client') and user.client:
        username = getattr(user.client, 'company_name', 'User')
    
    return send_email(
        'Verify Your Email',
        user.email,
        'verify_email',
        username=username,
        verification_url=verification_url
    )

def send_password_reset_email(user):
    """Send password reset link to user"""
    token = secrets.token_urlsafe(32)
    user.password_reset_token = token
    user.password_reset_expires = now_eest() + timedelta(hours=1)
    
    from app import db
    db.session.commit()
    
    reset_url = url_for(
        'auth.reset_password',
        token=token,
        _external=True
    )
    
    return send_email(
        'Reset Your Password',
        user.email,
        'reset_password',
        username=user.username,
        reset_url=reset_url
    )
