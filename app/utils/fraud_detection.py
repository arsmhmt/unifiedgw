"""
Fraud Detection Service for CPGateway
Advanced algorithms for detecting suspicious patterns and potential fraud
"""

import logging
from datetime import datetime, timedelta
from ..utils.timezone import now_eest
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from enum import Enum
import statistics
from sqlalchemy import func, and_, or_

from app.models.withdrawal import WithdrawalRequest, WithdrawalStatus
from app.models.client import Client
from app.models.user import User
from app.models.payment import Payment
from app.utils.audit import log_security_event
from app.extensions import db

logger = logging.getLogger(__name__)

class FraudRiskLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class FraudAlert:
    risk_level: FraudRiskLevel
    risk_score: int
    alert_type: str
    description: str
    entity_type: str  # 'withdrawal', 'client', 'user'
    entity_id: int
    factors: List[str]
    recommended_action: str
    metadata: Dict[str, Any]

class FraudDetectionService:
    """Main fraud detection service with multiple detection algorithms"""
    
    def __init__(self):
        self.risk_thresholds = {
            FraudRiskLevel.LOW: 0,
            FraudRiskLevel.MEDIUM: 30,
            FraudRiskLevel.HIGH: 60,
            FraudRiskLevel.CRITICAL: 85
        }
    
    def analyze_withdrawal_request(self, withdrawal: WithdrawalRequest) -> FraudAlert:
        """
        Comprehensive fraud analysis for withdrawal requests
        
        Args:
            withdrawal: WithdrawalRequest instance
            
        Returns:
            FraudAlert with risk assessment
        """
        risk_score = 0
        risk_factors = []
        metadata = {}
        
        # 1. Amount-based analysis
        amount_risk, amount_factors, amount_meta = self._analyze_withdrawal_amount(withdrawal)
        risk_score += amount_risk
        risk_factors.extend(amount_factors)
        metadata.update(amount_meta)
        
        # 2. Frequency analysis
        freq_risk, freq_factors, freq_meta = self._analyze_withdrawal_frequency(withdrawal)
        risk_score += freq_risk
        risk_factors.extend(freq_factors)
        metadata.update(freq_meta)
        
        # 3. Pattern analysis
        pattern_risk, pattern_factors, pattern_meta = self._analyze_withdrawal_patterns(withdrawal)
        risk_score += pattern_risk
        risk_factors.extend(pattern_factors)
        metadata.update(pattern_meta)
        
        # 4. Client behavior analysis
        client_risk, client_factors, client_meta = self._analyze_client_behavior(withdrawal)
        risk_score += client_risk
        risk_factors.extend(client_factors)
        metadata.update(client_meta)
        
        # 5. Time-based analysis
        time_risk, time_factors, time_meta = self._analyze_timing_patterns(withdrawal)
        risk_score += time_risk
        risk_factors.extend(time_factors)
        metadata.update(time_meta)
        
        # Determine risk level
        risk_level = self._calculate_risk_level(risk_score)
        
        # Generate recommendations
        recommended_action = self._get_recommended_action(risk_level, risk_factors)
        
        alert = FraudAlert(
            risk_level=risk_level,
            risk_score=min(risk_score, 100),  # Cap at 100
            alert_type="withdrawal_fraud_check",
            description=f"Fraud analysis for withdrawal #{withdrawal.id}",
            entity_type="withdrawal",
            entity_id=withdrawal.id,
            factors=risk_factors,
            recommended_action=recommended_action,
            metadata=metadata
        )
        
        # Log if high risk
        if risk_level in [FraudRiskLevel.HIGH, FraudRiskLevel.CRITICAL]:
            log_security_event(
                event_type='high_risk_withdrawal_detected',
                details={
                    'withdrawal_id': withdrawal.id,
                    'client_id': withdrawal.client_id,
                    'amount': withdrawal.amount,
                    'risk_score': risk_score,
                    'risk_level': risk_level.value,
                    'risk_factors': risk_factors
                },
                severity='high' if risk_level == FraudRiskLevel.HIGH else 'critical'
            )
        
        return alert
    
    def _analyze_withdrawal_amount(self, withdrawal: WithdrawalRequest) -> Tuple[int, List[str], Dict]:
        """Analyze withdrawal amount for suspicious patterns"""
        risk_score = 0
        factors = []
        metadata = {}
        
        amount = withdrawal.amount
        client_id = withdrawal.client_id
        
        # Get historical withdrawals for comparison
        historical = WithdrawalRequest.query.filter(
            WithdrawalRequest.client_id == client_id,
            WithdrawalRequest.id != withdrawal.id,
            WithdrawalRequest.status != WithdrawalStatus.REJECTED
        ).all()
        
        if historical:
            amounts = [w.amount for w in historical]
            avg_amount = statistics.mean(amounts)
            max_amount = max(amounts)
            
            metadata['historical_avg'] = avg_amount
            metadata['historical_max'] = max_amount
            metadata['historical_count'] = len(amounts)
            
            # Unusually high amount
            if amount > avg_amount * 5:
                risk_score += 25
                factors.append("amount_5x_higher_than_average")
            elif amount > avg_amount * 3:
                risk_score += 15
                factors.append("amount_3x_higher_than_average")
            
            # Highest ever withdrawal
            if amount > max_amount * 1.5:
                risk_score += 20
                factors.append("highest_withdrawal_ever")
        
        # Round number analysis (often suspicious)
        if amount % 1000 == 0 and amount >= 5000:
            risk_score += 10
            factors.append("large_round_number")
        elif amount % 500 == 0 and amount >= 2000:
            risk_score += 5
            factors.append("medium_round_number")
        
        # Very large amounts
        if amount >= 50000:
            risk_score += 30
            factors.append("very_large_amount")
        elif amount >= 20000:
            risk_score += 15
            factors.append("large_amount")
        
        return risk_score, factors, metadata
    
    def _analyze_withdrawal_frequency(self, withdrawal: WithdrawalRequest) -> Tuple[int, List[str], Dict]:
        """Analyze withdrawal frequency patterns"""
        risk_score = 0
        factors = []
        metadata = {}
        
        client_id = withdrawal.client_id
        now = now_eest()
        
        # Check different time windows
        windows = {
            'last_hour': timedelta(hours=1),
            'last_24h': timedelta(hours=24),
            'last_week': timedelta(days=7),
            'last_month': timedelta(days=30)
        }
        
        for window_name, window_duration in windows.items():
            since = now - window_duration
            
            count = WithdrawalRequest.query.filter(
                WithdrawalRequest.client_id == client_id,
                WithdrawalRequest.created_at >= since,
                WithdrawalRequest.status != WithdrawalStatus.REJECTED
            ).count()
            
            metadata[f'count_{window_name}'] = count
            
            # Define thresholds for each window
            thresholds = {
                'last_hour': (2, 5),
                'last_24h': (5, 10),
                'last_week': (15, 25),
                'last_month': (30, 50)
            }
            
            warning_threshold, critical_threshold = thresholds[window_name]
            
            if count >= critical_threshold:
                risk_score += 25
                factors.append(f"very_high_frequency_{window_name}")
            elif count >= warning_threshold:
                risk_score += 15
                factors.append(f"high_frequency_{window_name}")
        
        return risk_score, factors, metadata
    
    def _analyze_withdrawal_patterns(self, withdrawal: WithdrawalRequest) -> Tuple[int, List[str], Dict]:
        """Analyze patterns in withdrawal behavior"""
        risk_score = 0
        factors = []
        metadata = {}
        
        client_id = withdrawal.client_id
        
        # Get recent withdrawals (last 30 days)
        recent = WithdrawalRequest.query.filter(
            WithdrawalRequest.client_id == client_id,
            WithdrawalRequest.created_at >= now_eest() - timedelta(days=30),
            WithdrawalRequest.id != withdrawal.id
        ).order_by(WithdrawalRequest.created_at.desc()).all()
        
        if len(recent) >= 3:
            # Analyze patterns
            amounts = [w.amount for w in recent]
            times = [w.created_at.hour for w in recent]
            
            # Same amounts pattern
            if len(set(amounts)) == 1:  # All same amount
                risk_score += 20
                factors.append("identical_amounts_pattern")
            elif len(set(amounts)) <= len(amounts) / 3:  # Very few unique amounts
                risk_score += 10
                factors.append("repetitive_amounts_pattern")
            
            # Same time pattern
            if len(set(times)) <= 2:  # All at same 1-2 hours
                risk_score += 15
                factors.append("same_time_pattern")
            
            # Escalating amounts
            if amounts == sorted(amounts):  # Strictly increasing
                risk_score += 10
                factors.append("escalating_amounts_pattern")
            
            metadata['recent_amounts'] = amounts
            metadata['recent_times'] = times
        
        # Check for weekend/holiday patterns
        if withdrawal.created_at.weekday() >= 5:  # Weekend
            risk_score += 5
            factors.append("weekend_withdrawal")
        
        # Late night withdrawals
        hour = withdrawal.created_at.hour
        if hour >= 23 or hour <= 5:
            risk_score += 10
            factors.append("late_night_withdrawal")
        
        return risk_score, factors, metadata
    
    def _analyze_client_behavior(self, withdrawal: WithdrawalRequest) -> Tuple[int, List[str], Dict]:
        """Analyze client-specific behavior patterns"""
        risk_score = 0
        factors = []
        metadata = {}
        
        client = withdrawal.client
        if not client:
            risk_score += 30
            factors.append("client_not_found")
            return risk_score, factors, metadata
        
        metadata['client_id'] = client.id
        metadata['client_verified'] = client.is_verified
        metadata['client_active'] = client.is_active
        
        # Client verification status
        if not client.is_verified:
            risk_score += 25
            factors.append("unverified_client")
        
        # Client status
        if not client.is_active:
            risk_score += 35
            factors.append("inactive_client")
        
        # New client (registered recently)
        if client.created_at >= now_eest() - timedelta(days=7):
            risk_score += 20
            factors.append("new_client")
        elif client.created_at >= now_eest() - timedelta(days=30):
            risk_score += 10
            factors.append("recently_registered_client")
        
        # Check client balance vs withdrawal amount
        if hasattr(client, 'balance') and client.balance:
            if withdrawal.amount > client.balance:
                risk_score += 40
                factors.append("withdrawal_exceeds_balance")
            elif withdrawal.amount > client.balance * 0.8:
                risk_score += 15
                factors.append("withdrawal_most_of_balance")
            
            metadata['client_balance'] = float(client.balance)
            metadata['withdrawal_to_balance_ratio'] = withdrawal.amount / client.balance
        
        return risk_score, factors, metadata
    
    def _analyze_timing_patterns(self, withdrawal: WithdrawalRequest) -> Tuple[int, List[str], Dict]:
        """Analyze timing-based fraud indicators"""
        risk_score = 0
        factors = []
        metadata = {}
        
        # Check for withdrawals immediately after deposits
        # This would require deposit tracking - placeholder for now
        # recent_deposits = get_recent_deposits(withdrawal.client_id, hours=24)
        # if not recent_deposits and withdrawal.amount > 1000:
        #     risk_score += 20
        #     factors.append("withdrawal_without_recent_deposits")
        
        # Rapid succession withdrawals
        last_withdrawal = WithdrawalRequest.query.filter(
            WithdrawalRequest.client_id == withdrawal.client_id,
            WithdrawalRequest.id != withdrawal.id,
            WithdrawalRequest.created_at >= now_eest() - timedelta(minutes=30)
        ).first()
        
        if last_withdrawal:
            time_diff = (withdrawal.created_at - last_withdrawal.created_at).total_seconds() / 60
            metadata['minutes_since_last_withdrawal'] = time_diff
            
            if time_diff < 5:
                risk_score += 25
                factors.append("rapid_succession_withdrawals")
            elif time_diff < 15:
                risk_score += 15
                factors.append("quick_succession_withdrawals")
        
        return risk_score, factors, metadata
    
    def _calculate_risk_level(self, risk_score: int) -> FraudRiskLevel:
        """Calculate risk level based on score"""
        if risk_score >= 85:
            return FraudRiskLevel.CRITICAL
        elif risk_score >= 60:
            return FraudRiskLevel.HIGH
        elif risk_score >= 30:
            return FraudRiskLevel.MEDIUM
        else:
            return FraudRiskLevel.LOW
    
    def _get_recommended_action(self, risk_level: FraudRiskLevel, factors: List[str]) -> str:
        """Get recommended action based on risk assessment"""
        if risk_level == FraudRiskLevel.CRITICAL:
            return "BLOCK - Immediate manual review required"
        elif risk_level == FraudRiskLevel.HIGH:
            return "HOLD - Manual approval required"
        elif risk_level == FraudRiskLevel.MEDIUM:
            return "REVIEW - Enhanced verification recommended"
        else:
            return "PROCEED - Standard processing"
    
    def check_multiple_failed_logins(self, identifier: str, threshold: int = 5) -> bool:
        """
        Check for multiple failed login attempts
        
        Args:
            identifier: Username, email, or IP address
            threshold: Number of failed attempts to trigger alert
            
        Returns:
            True if threshold exceeded
        """
        from app.utils.security import AbuseProtection
        
        is_suspicious = AbuseProtection.detect_suspicious_activity(
            user_id=0,  # Use 0 for login attempts without user ID
            activity_type=f'login_failed_{identifier}',
            threshold=threshold,
            window=900  # 15 minutes
        )
        
        if is_suspicious:
            log_security_event(
                event_type='multiple_failed_logins',
                details={
                    'identifier': identifier,
                    'threshold': threshold,
                    'window_minutes': 15
                },
                severity='high'
            )
        
        return is_suspicious
    
    def analyze_api_usage_anomalies(self, api_key: str, hours: int = 24) -> List[Dict]:
        """
        Analyze API usage for anomalies
        
        Args:
            api_key: API key to analyze
            hours: Hours to look back
            
        Returns:
            List of anomalies detected
        """
        anomalies = []
        
        # This would integrate with API usage logging
        # For now, return placeholder
        
        return anomalies

# Global fraud detection service instance
fraud_detector = FraudDetectionService()

def analyze_withdrawal_fraud(withdrawal: WithdrawalRequest) -> FraudAlert:
    """
    Convenience function to analyze withdrawal for fraud
    
    Args:
        withdrawal: WithdrawalRequest to analyze
        
    Returns:
        FraudAlert with analysis results
    """
    return fraud_detector.analyze_withdrawal_request(withdrawal)

def should_block_withdrawal(withdrawal: WithdrawalRequest) -> Tuple[bool, str]:
    """
    Determine if withdrawal should be blocked based on fraud analysis
    
    Args:
        withdrawal: WithdrawalRequest to check
        
    Returns:
        (should_block, reason)
    """
    alert = analyze_withdrawal_fraud(withdrawal)
    
    should_block = alert.risk_level in [FraudRiskLevel.HIGH, FraudRiskLevel.CRITICAL]
    reason = f"Fraud risk: {alert.risk_level.value} (score: {alert.risk_score})"
    
    return should_block, reason
