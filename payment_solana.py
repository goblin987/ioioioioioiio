import logging
import json
import time
import asyncio
import requests
import os
from decimal import Decimal
from solana.rpc.api import Client
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.system_program import TransferParams, transfer
from solders.transaction import Transaction
from utils import get_db_connection, send_message_with_retry, format_currency

# --- CONFIGURATION ---
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
ADMIN_WALLET = os.getenv("SOLANA_ADMIN_WALLET") # Must be set in Render
ENABLE_AUTO_SWEEP = True # Automatically send funds to admin wallet after payment

logger = logging.getLogger(__name__)
client = Client(SOLANA_RPC_URL)

def get_sol_price_eur():
    """Fetch current SOL price in EUR from CoinGecko with Binance fallback"""
    # 1. Try CoinGecko
    try:
        response = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=eur", 
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if 'solana' in data and 'eur' in data['solana']:
                return Decimal(str(data['solana']['eur']))
            else:
                logger.error(f"CoinGecko unexpected response: {data}")
        else:
            logger.warning(f"CoinGecko returned status {response.status_code}")
    except Exception as e:
        logger.error(f"Error fetching SOL price from CoinGecko: {e}")

    # 2. Try Binance Fallback
    try:
        response = requests.get(
            "https://api.binance.com/api/v3/ticker/price?symbol=SOLEUR", 
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if 'price' in data:
                return Decimal(str(data['price']))
    except Exception as e:
        logger.error(f"Error fetching SOL price from Binance: {e}")

    # 3. Try CryptoCompare Fallback
    try:
        response = requests.get(
            "https://min-api.cryptocompare.com/data/price?fsym=SOL&tsyms=EUR",
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            if 'EUR' in data:
                return Decimal(str(data['EUR']))
    except Exception as e:
        logger.error(f"Error fetching SOL price from CryptoCompare: {e}")

    return None

async def create_solana_payment(user_id, order_id, eur_amount):
    """
    Generates a unique SOL wallet for this transaction.
    Returns: dict with address, amount, and qr_code data
    """
    price = get_sol_price_eur()
    if not price:
        logger.error("Could not fetch SOL price, using fallback or failing.")
        return {'error': 'estimate_failed'}

    # Calculate SOL amount (add small buffer or just exact)
    # Quantize to 9 decimal places (lamports)
    sol_amount = (Decimal(eur_amount) / price).quantize(Decimal("0.000000001"))
    
    # Generate new Keypair
    kp = Keypair()
    pubkey = str(kp.pubkey())
    # Store private key as list of integers for storage
    private_key_json = json.dumps(list(bytes(kp)))

    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Check if order_id already exists (retry case)
        c.execute("SELECT public_key, expected_amount FROM solana_wallets WHERE order_id = %s", (order_id,))
        existing = c.fetchone()
        
        if existing:
            logger.info(f"Found existing Solana wallet for order {order_id}")
            return {
                'pay_address': existing['public_key'],
                'pay_amount': str(existing['expected_amount']),
                'pay_currency': 'SOL',
                'exchange_rate': float(price),
                'payment_id': order_id # Use order_id as payment_id
            }

        c.execute("""
            INSERT INTO solana_wallets (user_id, order_id, public_key, private_key, expected_amount, status)
            VALUES (%s, %s, %s, %s, %s, 'pending')
        """, (user_id, order_id, pubkey, private_key_json, float(sol_amount)))
        conn.commit()
    except Exception as e:
        logger.error(f"DB Error creating solana payment: {e}")
        return {'error': 'internal_server_error'}
    finally:
        conn.close()

    return {
        'pay_address': pubkey,
        'pay_amount': str(sol_amount),
        'pay_currency': 'SOL',
        'exchange_rate': float(price),
        'payment_id': order_id
    }

async def check_solana_deposits(context):
    """
    Background task to check all pending wallets for deposits.
    Call this periodically (e.g., every 30-60 seconds).
    """
    conn = get_db_connection()
    c = conn.cursor()
    
    try:
        # Get pending wallets
        # Assuming RealDictCursor from utils
        c.execute("SELECT * FROM solana_wallets WHERE status = 'pending'")
        pending = c.fetchall()
        
        if not pending:
            return

        for wallet in pending:
            try:
                pubkey_str = wallet['public_key']
                expected = Decimal(str(wallet['expected_amount']))
                wallet_id = wallet['id']
                order_id = wallet['order_id']
                user_id = wallet['user_id']
                
                # Check Balance (RPC call)
                # Note: get_balance returns lamports (1 SOL = 10^9 lamports)
                try:
                    balance_resp = client.get_balance(Pubkey.from_string(pubkey_str))
                    lamports = balance_resp.value
                    sol_balance = Decimal(lamports) / Decimal(10**9)
                except Exception as rpc_e:
                    logger.warning(f"RPC Error checking wallet {pubkey_str}: {rpc_e}")
                    continue
                
                # Check if Paid (allowing very small tolerance, e.g. 99.5%)
                # Or check if received > 0.99 * expected
                if sol_balance > 0 and sol_balance >= (expected * Decimal("0.99")):
                    logger.info(f"✅ Payment detected for Order {order_id}: {sol_balance} SOL")
                    
                    # 1. Mark as Paid in DB
                    c.execute("UPDATE solana_wallets SET status = 'paid', amount_received = %s, updated_at = NOW() WHERE id = %s", (float(sol_balance), wallet_id))
                    conn.commit()
                    
                    # 2. Trigger Payment Success Logic
                    # Import here to avoid circular dependency
                    from payment import process_successful_crypto_purchase, process_successful_refill
                    
                    # Determine if it's a purchase or refill based on order_id prefix
                    # Assuming order_id format like "PURCHASE_uuid" or "REFILL_uuid"
                    # If order_id isn't descriptive, we need to look up pending_deposits table using order_id as payment_id
                    
                    c.execute("SELECT is_purchase, basket_snapshot, discount_code FROM pending_deposits WHERE payment_id = %s", (order_id,))
                    deposit_info = c.fetchone()
                    
                    if deposit_info:
                        is_purchase = deposit_info['is_purchase']
                        
                        if is_purchase:
                            # Reconstruct basket snapshot if stored as JSON string
                            basket_snapshot = deposit_info.get('basket_snapshot')
                            if isinstance(basket_snapshot, str):
                                try: basket_snapshot = json.loads(basket_snapshot)
                                except: pass
                                
                            discount_code = deposit_info.get('discount_code')
                            
                            await process_successful_crypto_purchase(user_id, basket_snapshot, discount_code, order_id, context)
                        else:
                            # Refill
                            # We need to calculate EUR amount. Use the stored rate or current rate?
                            # Ideally we stored the target EUR amount in pending_deposits
                            c.execute("SELECT amount_eur FROM pending_deposits WHERE payment_id = %s", (order_id,))
                            amount_res = c.fetchone()
                            amount_eur = Decimal(str(amount_res['amount_eur'])) if amount_res else Decimal("0.0")
                            
                            await process_successful_refill(user_id, amount_eur, order_id, context)
                    else:
                        logger.error(f"Could not find pending_deposit record for solana order {order_id}")
                    
                    # 3. Sweep Funds (Optional but recommended)
                    if ENABLE_AUTO_SWEEP and ADMIN_WALLET:
                        # Run sweep in background
                        asyncio.create_task(sweep_wallet(wallet, lamports))
                        
            except Exception as e:
                logger.error(f"Error checking wallet {wallet.get('public_key')}: {e}", exc_info=True)
                
    except Exception as e:
        logger.error(f"Error in check_solana_deposits loop: {e}", exc_info=True)
    finally:
        conn.close()

async def sweep_wallet(wallet_data, current_lamports):
    """Moves funds from temp wallet to ADMIN_WALLET"""
    try:
        if current_lamports < 5000: # Ignore dust (less than 0.000005 SOL)
            return

        # Load Keypair
        priv_key_list = json.loads(wallet_data['private_key'])
        kp = Keypair.from_bytes(bytes(priv_key_list))
        
        # Calculate fee (simple transfer is usually 5000 lamports)
        fee = 5000
        amount_to_send = current_lamports - fee
        
        if amount_to_send <= 0:
            return

        logger.info(f"🧹 Sweeping {amount_to_send} lamports from {wallet_data['public_key']} to {ADMIN_WALLET}...")

        # Create Transaction using solders
        ix = transfer(
            TransferParams(
                from_pubkey=kp.pubkey(),
                to_pubkey=Pubkey.from_string(ADMIN_WALLET),
                lamports=int(amount_to_send)
            )
        )
        
        # Get blockhash
        latest_blockhash = client.get_latest_blockhash().value.blockhash
        
        # Construct and sign transaction
        transaction = Transaction.new_signed_with_payer(
            [ix],
            kp.pubkey(),
            [kp],
            latest_blockhash
        )
        
        # Send
        txn_sig = client.send_transaction(transaction)
        
        logger.info(f"✅ Swept funds. Sig: {txn_sig.value}")
        
        # Update DB
        conn = get_db_connection()
        conn.cursor().execute("UPDATE solana_wallets SET status = 'swept' WHERE id = %s", (wallet_data['id'],))
        conn.commit()
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ Failed to sweep wallet {wallet_data['public_key']}: {e}", exc_info=True)

