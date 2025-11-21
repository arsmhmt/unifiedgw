from datetime import datetime, timedelta
from ..utils.timezone import now_eest
from apscheduler.schedulers.background import BackgroundScheduler

from app.models import CommissionSnapshot
from app.models.client import Client
from app.utils.finance import FinanceCalculator
from app.extensions import db

# Initialize scheduler
scheduler = BackgroundScheduler()

@scheduler.scheduled_job('cron', day='1', hour='0')
def create_monthly_commission_snapshots():
    """
    Create monthly commission snapshots for all clients on the first day of each month
    """
    print("Creating monthly commission snapshots...")
    
    try:
        # Get all active clients
        clients = Client.query.all()
        
        for client in clients:
            try:
                # Calculate commissions
                deposit_commission, withdrawal_commission, total_commission = FinanceCalculator().calculate_commission(client.id)
                
                # Create snapshot for this client
                now = now_eest()
                first_day = now.replace(day=1)
                last_month = first_day - timedelta(days=1)
                start_of_month = last_month.replace(day=1)
                
                snapshot = CommissionSnapshot(
                    client_id=client.id,
                    period_start=start_of_month,
                    period_end=last_month,
                    deposit_commission=float(deposit_commission),
                    withdrawal_commission=float(withdrawal_commission),
                    total_commission=float(total_commission)
                )
                db.session.add(snapshot)
                db.session.commit()
                print(f"Created snapshot for client {client.id}: {total_commission} USDT")
            except Exception as e:
                print(f"Error creating snapshot for client {client.id}: {str(e)}")

        print("Commission snapshot creation completed.")
    except Exception as e:
        print(f"Error in create_monthly_commission_snapshots: {str(e)}")

# Start the scheduler
def start_scheduler():
    """
    Start the background scheduler
    """
    try:
        scheduler.start()
        print("Scheduled tasks started successfully.")
    except Exception as e:
        print(f"Error starting scheduler: {str(e)}")

# Create initial snapshots for existing clients
def create_initial_snapshots():
    """
    Create initial snapshots for all existing clients
    """
    print("Creating initial commission snapshots...")
    
    try:
        # Get all active clients
        clients = Client.query.all()
        
        for client in clients:
            try:
                # Calculate commissions
                deposit_commission, withdrawal_commission, total_commission = FinanceCalculator().calculate_commission(client.id)
                
                # Create snapshot for this client
                now = now_eest()
                first_day = now.replace(day=1)
                last_month = first_day - timedelta(days=1)
                start_of_month = last_month.replace(day=1)
                
                snapshot = CommissionSnapshot(
                    client_id=client.id,
                    period_start=start_of_month,
                    period_end=last_month,
                    deposit_commission=float(deposit_commission),
                    withdrawal_commission=float(withdrawal_commission),
                    total_commission=float(total_commission)
                )
                db.session.add(snapshot)
                db.session.commit()
                print(f"Created initial snapshot for client {client.id}: {total_commission} USDT")
            except Exception as e:
                print(f"Error creating initial snapshot for client {client.id}: {str(e)}")
        
        print("Initial snapshot creation completed.")
    except Exception as e:
        print(f"Error in create_initial_snapshots: {str(e)}")
