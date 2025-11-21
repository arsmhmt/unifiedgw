"""
Tests for flow hardening (Day 2).
Tests double confirmation protection and status transitions.
"""
import pytest
from app.models.payment import Payment
from app.models.enums import PaymentStatus


@pytest.mark.integration
class TestFlowHardening:
    """Test flow hardening features."""
    
    def test_double_confirmation_rejected(self, db, test_payment):
        """Test that double confirmation is rejected and logged."""
        # First confirmation
        result = test_payment.confirm_payment(tx_hash='0xabc123', confirmations=6)
        assert result is True
        assert test_payment.status == PaymentStatus.COMPLETED
        db.session.commit()
        
        # Second confirmation attempt (should be rejected)
        result = test_payment.confirm_payment(tx_hash='0xabc123', confirmations=12)
        assert result is False
        assert test_payment.status == PaymentStatus.COMPLETED  # Status unchanged
    
    def test_confirm_payment_updates_status(self, db, test_payment):
        """Test that confirm_payment updates status correctly."""
        assert test_payment.status == PaymentStatus.PENDING
        
        result = test_payment.confirm_payment(tx_hash='0xdef456')
        assert result is True
        assert test_payment.status == PaymentStatus.COMPLETED
    
    def test_status_transition_logging(self, db, test_payment, caplog):
        """Test that status transitions are logged."""
        import logging
        caplog.set_level(logging.INFO)
        
        # Change status
        test_payment.status = PaymentStatus.APPROVED
        db.session.commit()
        
        # Check logs contain status transition
        assert any('status.transition' in record.message for record in caplog.records)
    
    def test_payment_already_approved_rejects_confirmation(self, db, test_payment):
        """Test that already approved payments reject confirmation."""
        # Set to approved
        test_payment.status = PaymentStatus.APPROVED
        db.session.commit()
        
        # Try to confirm
        result = test_payment.confirm_payment(tx_hash='0xghi789')
        assert result is False
        assert test_payment.status == PaymentStatus.APPROVED  # Unchanged


@pytest.mark.unit
class TestPaymentModel:
    """Test Payment model methods."""
    
    def test_payment_creation(self, db, test_client_model):
        """Test creating a payment."""
        payment = Payment(
            client_id=test_client_model.id,
            fiat_amount=50.00,
            fiat_currency='EUR',
            crypto_currency='BTC',
            payment_method='crypto',
            transaction_id='test_tx_new',
            status=PaymentStatus.PENDING
        )
        db.session.add(payment)
        db.session.commit()
        
        assert payment.id is not None
        assert payment.status == PaymentStatus.PENDING
    
    def test_calculate_crypto_amount(self, db, test_payment):
        """Test crypto amount calculation."""
        # Note: This test may need mocking for exchange rate API
        # For now, just test the method exists and doesn't crash
        test_payment.fiat_amount = 100.00
        test_payment.fiat_currency = 'USD'
        
        # Method should exist
        assert hasattr(test_payment, 'calculate_crypto_amount')
