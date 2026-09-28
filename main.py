from fastapi import FastAPI
import sqlite3 # we import notebook handler
from fastapi.middleware.cors import CORSMiddleware # CORS = Cross-Origin Resource Sharing (Bouncer)
from datetime import datetime

app = FastAPI()

#Allow React (the frontend) to talk to python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

#FUNCTION TO OPEN NOTEBOOK - we will use it everywhere
def get_db():
    conn = sqlite3.connect("bank.db", check_same_thread=False) 
    return conn

#RUN THIS ONCE SERVER STARTS: Create table if it doesn't exists
conn = get_db()
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        owner TEXT PRIMARY KEY,
        balance INTEGER
    )
""")
# NEW TABLE - OUR RECEIPT BOOK
cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        from_owner TEXT,
        to_owner TEXT,
        amount INTEGER,
        time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
""")
conn.commit() # commit = save permanently with gum, not pencil
conn.close()

# 1. CREATE ACCOUNT
@app.post("/create_account/{owner_name}/{initial_deposit}")
def create_account(owner_name: str, initial_deposit: int):
    conn = get_db()
    cursor = conn.cursor()
    #Check if owner already exists
    cursor.execute("SELECT * FROM accounts WHERE owner =?", (owner_name,))
    exists = cursor.fetchone() # fetchone = bring one row if it exists
    if exists:
        conn.close()
        return {"error": "Account already exists!"}

    # Insert new row
    cursor.execute("INSERT INTO accounts (owner, balance) VALUES (?,?)", (owner_name, initial_deposit))
    conn.commit()
    conn.close()
    return {"message": f"Account created for {owner_name} with ₦{initial_deposit}"}

# 2. CHECK BALANCE
@app.get("/balance/{owner_name}")
def balance(owner_name: str):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM accounts WHERE owner =?", (owner_name,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"balance": row[0]} #row[0] = first column which is balance
    else:
        return{"error": "Account not found!"}

# 3. DEPOSIT
@app.post("/deposit/{owner_name}/{amount}")
def deposit(owner_name: str, amount: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM accounts WHERE owner =?", (owner_name,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "Account not found"}

    new_balance = row[0] + amount
    cursor.execute("UPDATE accounts SET balance =? WHERE owner =?", (new_balance, owner_name))
    conn.commit()
    conn.close()
    return {"result": f"Deposited ₦{amount}", "new_balance": new_balance}

# 4. WITHDRAW
@app.post("/withdraw/{owner_name}/{amount}")
def withdraw(owner_name: str, amount: int):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM accounts WHERE owner =?", (owner_name,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return {"error": "Account not found!"}

    if row[0] < amount:
        conn.close()
        return {"error": 'Insufficient Funds!'}
    else:
        new_balance = row[0] - amount
        cursor.execute("UPDATE accounts SET balance =? WHERE owner =?", (new_balance, owner_name))
        conn.commit()
        conn.close()
        return {"result": f"Withdrew ₦{amount}", "new_balance": new_balance}



@app.get("/all_accounts")
def all_accounts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts")
    rows = cursor.fetchall()
    conn.close()
    return {"accounts": rows}

@app.post("/transfer")

def transfer(from_owner: str, to_owner: str, amount: int):
    conn = get_db()
    cursor = conn.cursor()

    # 1. check that both accounts exists
    cursor.execute("SELECT balance FROM accounts where owner=?", (from_owner,))
    sender = cursor.fetchone()
    cursor.execute("SELECT balance FROM accounts WHERE owner=?", (to_owner,))
    receiver = cursor.fetchone()

    if not sender or not receiver:
        conn.close()
        return {"error": "One of the accounts does not exist"}

    if sender[0] < amount:
        conn.close()
        return {"error": "Insufficient Funds!"}

    # 2. THE ATOMIC PART - All in one go!
    try:
        cursor.execute("UPDATE accounts SET balance = balance -? WHERE owner=?", (amount, from_owner))
        cursor.execute("UPDATE accounts SET balance = balance +? WHERE owner=?", (amount, to_owner))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO transactions (from_owner, to_owner, amount, timestamp) VALUES (?,?,?,?)", (from_owner, to_owner, amount, now))

        conn.commit() # Only one commit for all 3! Either all saved or none!

    except:
        conn.rollback() # if anything fails, UNDO everything!
        conn.close()
        return {"error": "Transfer Unsuccessful!"}

    conn.close()
    return {"message": f"Successfully Transferred {amount} from {from_owner} to {to_owner}"}

@app.get("/transactions")
def transactions():
    conn = get_db()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transactions")
    rows = cursor.fetchall()
    conn.close()
    result = [dict(row) for row in rows]
    return {"transactions": rows}