from ..utils.timezone import now_eest
from ..extensions import db
from datetime import datetime, timedelta
from enum import Enum
import json

class ReportType(Enum):
    PAYMENT_SUMMARY = 'payment_summary'
    CLIENT_ANALYSIS = 'client_analysis'
    REVENUE_TRENDS = 'revenue_trends'
    PAYMENT_METHODS = 'payment_methods'
    OVERDUE_PAYMENTS = 'overdue_payments'

class ReportStatus(Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'

class ReportFilterType(Enum):
    DATE_RANGE = 'date_range'
    CLIENT_GROUP = 'client_group'
    PAYMENT_STATUS = 'payment_status'
    PAYMENT_METHOD = 'payment_method'
    CURRENCY = 'currency'

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(255))
    report_type = db.Column(db.String(50), nullable=False)
    filters = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, name, description, report_type, filters=None):
        self.name = name
        self.description = description
        self.report_type = report_type
        self.filters = filters or {}

    def generate_report(self):
        """Generate the report based on type and filters"""
        if self.report_type == ReportType.PAYMENT_SUMMARY.value:
            return self._generate_payment_summary()
        elif self.report_type == ReportType.CLIENT_ANALYSIS.value:
            return self._generate_client_analysis()
        elif self.report_type == ReportType.REVENUE_TRENDS.value:
            return self._generate_revenue_trends()
        elif self.report_type == ReportType.PAYMENT_METHODS.value:
            return self._generate_payment_methods()
        elif self.report_type == ReportType.OVERDUE_PAYMENTS.value:
            return self._generate_overdue_payments()
        return None

    def _generate_payment_summary(self):
        from .payment import Payment
        """Generate payment summary report"""
        start_date = self.filters.get('start_date')
        end_date = self.filters.get('end_date')
        
        query = Payment.query
        if start_date:
            query = query.filter(Payment.created_at >= start_date)
        if end_date:
            query = query.filter(Payment.created_at <= end_date)
        
        payments = query.all()
        
        summary = {
            'total_payments': len(payments),
            'total_amount': sum(p.amount for p in payments),
            'by_status': {},
            'by_currency': {},
            'by_method': {}
        }
        
        for payment in payments:
            # Status breakdown
            summary['by_status'][payment.status] = summary['by_status'].get(payment.status, 0) + 1
            
            # Currency breakdown
            summary['by_currency'][payment.currency] = summary['by_currency'].get(payment.currency, 0) + payment.amount
            
            # Payment method breakdown
            key = f"{payment.payment_method} ({payment.payment_provider or 'N/A'})"
            summary['by_method'][key] = summary['by_method'].get(key, 0) + 1
        
        return summary

    def _generate_client_analysis(self):
        from .client import Client
        from .payment import Payment
        """Generate client analysis report"""
        start_date = self.filters.get('start_date')
        end_date = self.filters.get('end_date')
        
        query = Client.query
        if start_date:
            query = query.filter(Client.created_at >= start_date)
        if end_date:
            query = query.filter(Client.created_at <= end_date)
        
        clients = query.all()
        
        analysis = {
            'total_clients': len(clients),
            'active_clients': len([c for c in clients if c.is_active]),
            'payment_history': {},
            'recurring_payments': 0
        }
        
        for client in clients:
            payments = Payment.query.filter_by(client_id=client.id).all()
            analysis['payment_history'][client.id] = {
                'total_payments': len(payments),
                'total_amount': sum(p.amount for p in payments)
            }
            
            recurring = RecurringPayment.query.filter_by(client_id=client.id).count()
            analysis['recurring_payments'] += recurring
        
        return analysis

    def _generate_revenue_trends(self):
        from .payment import Payment
        """Generate revenue trends report"""
        start_date = self.filters.get('start_date')
        end_date = self.filters.get('end_date')
        
        if not start_date or not end_date:
            return None
            
        # Calculate date range
        date_range = (datetime.strptime(end_date, '%Y-%m-%d') - 
                     datetime.strptime(start_date, '%Y-%m-%d')).days + 1
        
        # Initialize trends data
        trends = {
            'daily': [],
            'weekly': [],
            'monthly': []
        }
        
        # Get payments within date range
        payments = Payment.query.filter(
            Payment.created_at >= start_date,
            Payment.created_at <= end_date
        ).all()
        
        # Calculate trends
        current_date = datetime.strptime(start_date, '%Y-%m-%d')
        while current_date <= datetime.strptime(end_date, '%Y-%m-%d'):
            # Daily trend
            daily_payments = [p for p in payments 
                            if p.created_at.date() == current_date.date()]
            trends['daily'].append({
                'date': current_date.strftime('%Y-%m-%d'),
                'amount': sum(p.amount for p in daily_payments)
            })
            
            # Weekly trend (if enough days)
            if len(trends['daily']) >= 7:
                weekly_amount = sum(d['amount'] for d in trends['daily'][-7:])
                trends['weekly'].append({
                    'week': f"{trends['daily'][-7]['date']} - {trends['daily'][-1]['date']}",
                    'amount': weekly_amount
                })
            
            # Monthly trend (if enough weeks)
            if len(trends['weekly']) >= 4:
                monthly_amount = sum(w['amount'] for w in trends['weekly'][-4:])
                trends['monthly'].append({
                    'month': f"{trends['weekly'][-4]['week'].split(' - ')[0][:7]}",
                    'amount': monthly_amount
                })
            
            current_date += timedelta(days=1)
        
        return trends

    def _generate_payment_methods(self):
        from .payment import Payment
        """Generate payment methods report"""
        start_date = self.filters.get('start_date')
        end_date = self.filters.get('end_date')
        
        query = Payment.query
        if start_date:
            query = query.filter(Payment.created_at >= start_date)
        if end_date:
            query = query.filter(Payment.created_at <= end_date)
        
        payments = query.all()
        
        methods = {}
        for payment in payments:
            key = f"{payment.payment_method} ({payment.payment_provider or 'N/A'})"
            if key not in methods:
                methods[key] = {
                    'count': 0,
                    'total_amount': 0,
                    'by_currency': {}
                }
            
            methods[key]['count'] += 1
            methods[key]['total_amount'] += payment.amount
            methods[key]['by_currency'][payment.currency] = (
                methods[key]['by_currency'].get(payment.currency, 0) + payment.amount
            )
        
        return methods

    def _generate_overdue_payments(self):
        from .payment import Payment
        """Generate overdue payments report"""
        current_time = now_eest()
        
        overdue_payments = Payment.query.filter(
            Payment.status == 'pending',
            Payment.due_date < current_time
        ).all()
        
        report = {
            'total_overdue': len(overdue_payments),
            'total_amount': sum(p.amount for p in overdue_payments),
            'by_age': {
                '1-7 days': [],
                '8-30 days': [],
                '31+ days': []
            }
        }
        
        for payment in overdue_payments:
            days_overdue = (current_time - payment.due_date).days
            if days_overdue <= 7:
                key = '1-7 days'
            elif days_overdue <= 30:
                key = '8-30 days'
            else:
                key = '31+ days'
            
            report['by_age'][key].append({
                'client': payment.client.name,
                'amount': payment.amount,
                'currency': payment.currency,
                'days_overdue': days_overdue,
                'due_date': payment.due_date.strftime('%Y-%m-%d')
            })
        
        return report
