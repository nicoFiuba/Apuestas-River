import os
import logging
import psycopg2
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(dotenv_path=BASE_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DATABASE_URL = os.getenv("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bets (
                id SERIAL PRIMARY KEY,
                match_name VARCHAR(255) NOT NULL,
                selection VARCHAR(100) NOT NULL,
                bookmaker VARCHAR(100) NOT NULL,
                odds NUMERIC(6,2) NOT NULL,
                ev_percentage NUMERIC(5,2) NOT NULL,
                stake_ars NUMERIC(10,2) NOT NULL,
                status VARCHAR(20) DEFAULT 'PENDING',
                profit_ars NUMERIC(10,2) DEFAULT 0.0,
                created_at TIMESTAMP NOT NULL
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS odds_history (
                id SERIAL PRIMARY KEY,
                match_name VARCHAR(255) NOT NULL,
                bookmaker VARCHAR(100) NOT NULL,
                odds NUMERIC(6,2) NOT NULL,
                created_at TIMESTAMP NOT NULL
            );
        """)
        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logging.error(f"Error al inicializar Supabase (PostgreSQL): {e}")


def record_bet(match_name: str, selection: str, bookmaker: str, odds: float, ev_percentage: float, stake_ars: float) -> int:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    query = """
        INSERT INTO bets (match_name, selection, bookmaker, odds, ev_percentage, stake_ars, status, profit_ars, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, 'PENDING', 0.0, %s) RETURNING id;
    """
    cursor.execute(query, (match_name, selection, bookmaker, odds, ev_percentage, stake_ars, now_str))
    
    bet_id = cursor.fetchone()[0]
    conn.commit()
    cursor.close()
    conn.close()
    return bet_id


def resolve_bet(bet_id: int, status: str) -> bool:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT odds, stake_ars FROM bets WHERE id = %s", (bet_id,))
    row = cursor.fetchone()
    if not row:
        cursor.close()
        conn.close()
        return False

    odds, stake = float(row[0]), float(row[1])
    status_upper = status.upper()

    if status_upper == "WIN":
        profit = (odds - 1.0) * stake
    elif status_upper == "LOSS":
        profit = -stake
    else:  # VOID
        profit = 0.0

    cursor.execute("""
        UPDATE bets
        SET status = %s, profit_ars = %s
        WHERE id = %s
    """, (status_upper, profit, bet_id))

    conn.commit()
    cursor.close()
    conn.close()
    return True


def get_performance_summary() -> dict:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*), SUM(stake_ars), SUM(profit_ars) FROM bets WHERE status IN ('WIN', 'LOSS')")
    row = cursor.fetchone()
    
    total_bets = row[0] or 0
    total_staked = float(row[1]) if row[1] else 0.0
    total_profit = float(row[2]) if row[2] else 0.0

    cursor.execute("SELECT COUNT(*) FROM bets WHERE status = 'WIN'")
    wins = cursor.fetchone()[0] or 0

    yield_pct = (total_profit / total_staked * 100.0) if total_staked > 0 else 0.0
    win_rate = (wins / total_bets * 100.0) if total_bets > 0 else 0.0

    cursor.close()
    conn.close()

    return {
        "total_bets": total_bets,
        "total_staked": round(total_staked, 2),
        "total_profit": round(total_profit, 2),
        "yield_percentage": round(yield_pct, 2),
        "win_rate": round(win_rate, 2)
    }


def save_odds_history(match_name: str, bookmaker: str, odds: float) -> str:
    init_db()
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        SELECT odds FROM odds_history 
        WHERE match_name = %s AND bookmaker = %s 
        ORDER BY id DESC LIMIT 1
    """, (match_name, bookmaker))
    
    row = cursor.fetchone()
    alert_type = None

    if row:
        prev_odds = float(row[0])
        diff_pct = ((odds - prev_odds) / prev_odds) * 100.0
        
        if diff_pct >= 5.0:
            alert_type = f"📈 *SUBIDA DE CUOTA (RISING):* Subió un `{diff_pct:.1f}%` (de `{prev_odds:.2f}` a `{odds:.2f}`)"
        elif diff_pct <= -5.0:
            alert_type = f"📉 *CAÍDA DE CUOTA (DROPPING):* Cayó un `{abs(diff_pct):.1f}%` (de `{prev_odds:.2f}` a `{odds:.2f}`)"

    cursor.execute("""
        INSERT INTO odds_history (match_name, bookmaker, odds, created_at)
        VALUES (%s, %s, %s, %s)
    """, (match_name, bookmaker, odds, now_str))

    conn.commit()
    cursor.close()
    conn.close()

    return alert_type


if __name__ == "__main__":
    init_db()
