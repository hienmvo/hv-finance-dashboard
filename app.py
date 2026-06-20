"""
Finance Dashboard — Flask backend
Supports: Chase, Bank of America CSV imports
"""

from flask import Flask, render_template, request, jsonify
import sqlite3
import os
import csv
import io
import re
import hashlib
import traceback
from datetime import datetime

app = Flask(__name__)
DB_PATH = os.path.join('data', 'finance.db')

# ─── CATEGORIES ──────────────────────────────────────────────────────────────

CATEGORY_COLORS = {
    # Income — emerald green family (specified: Income, ATM Deposit, Zelle In)
    'Income':            '#0F9D6B',  # bright emerald green
    'ATM Deposit':       '#8DD9B4',  # medium mint
    'Zelle In':          '#D6F0E1',  # pale mint
    'Investment In':     '#3DB88A',  # mid emerald, between Income and ATM Deposit
    'Tax Refund':        '#F6C90E',  # golden yellow — distinct from greens
    'Wire Transfer In':  '#6ECFB3',  # light teal-green
    'Cash Rewards':      '#A8D96B',  # yellow-green
    'Other Income':      '#B0D9C5',  # soft sage, distinct from ATM Deposit
    # Expense — reds/purples/blues (specified: Rent, CC, Zelle Out, Other, Groceries, Utilities, Dining)
    'Rent/Mortgage':       '#A32D2D',  # dark red
    'Credit Card Payment': '#E24B4A',  # standard red
    'Zelle Out':           '#6A60C9',  # purple
    'Other Expense':       '#85B7EB',  # soft blue
    'Groceries':           '#97C459',  # green
    'Utilities':           '#FAC775',  # amber
    'Dining Out':          '#5DCAA5',  # teal
    'Insurance':           '#7BA7D0',  # steel blue (lighter than Other Expense)
    'ATM Withdrawal':      '#E8956D',  # warm orange
    'Bank Fee':            '#9BAAB8',  # steel gray
    'Taxes':               '#8B2252',  # deep burgundy/magenta
    'Wire Transfer Out':   '#D4637A',  # rose red
    'Investment Out':      '#92B4DB',  # periwinkle blue
    # Special
    'Internal Transfer':   '#E2E8F0',
    'Ignore':              '#D1D5DB',
}

INCOME_CATEGORIES = [
    'Income',
    'Zelle In',
    'ATM Deposit',
    'Tax Refund',
    'Cash Rewards',
    'Wire Transfer In',
    'Investment In',
    'Other Income',
]
EXPENSE_CATEGORIES = [
    'Rent/Mortgage',
    'Groceries',
    'Dining Out',
    'Utilities',
    'Insurance',
    'Zelle Out',
    'ATM Withdrawal',
    'Credit Card Payment',
    'Bank Fee',
    'Taxes',
    'Wire Transfer Out',
    'Investment Out',
    'Other Expense',
]
SPECIAL_CATEGORIES = ['Internal Transfer', 'Ignore']
ALL_CATEGORIES = INCOME_CATEGORIES + EXPENSE_CATEGORIES + SPECIAL_CATEGORIES


# ─── DATABASE ─────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_db():
    os.makedirs('data', exist_ok=True)
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            bank        TEXT    NOT NULL,
            date        TEXT    NOT NULL,
            description TEXT    NOT NULL,
            amount      REAL    NOT NULL,
            tx_type     TEXT    DEFAULT \'\',
            category    TEXT    NOT NULL DEFAULT \'Other Expense\',
            is_internal INTEGER DEFAULT 0,
            notes       TEXT    DEFAULT \'\',
            hash        TEXT    UNIQUE NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_date     ON transactions(date);
        CREATE INDEX IF NOT EXISTS idx_bank     ON transactions(bank);
        CREATE INDEX IF NOT EXISTS idx_category ON transactions(category);

        CREATE TABLE IF NOT EXISTS category_rules (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern    TEXT    NOT NULL UNIQUE,
            category   TEXT    NOT NULL,
            created_at TEXT    DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    # Migration: re-categorize Webull/Wealthfront withdrawals already in DB
    conn.execute('''
        UPDATE transactions
        SET category = \'Internal Transfer\', is_internal = 1
        WHERE category = \'Investment In\'
        AND (LOWER(description) LIKE \'%webull%\' OR LOWER(description) LIKE \'%wealthfront%\')
    ''')
    # Migration: re-hide Chase CC payments when CC is already uploaded
    conn.execute('''
        UPDATE transactions
        SET category = \'Internal Transfer\', is_internal = 1
        WHERE bank = \'Chase\' AND is_internal = 0
        AND (LOWER(description) LIKE \'%payment to chase card%\' OR tx_type = \'LOAN_PMT\')
        AND EXISTS (SELECT 1 FROM transactions WHERE bank = \'Chase CC\' LIMIT 1)
    ''')
    conn.commit()
    conn.close()

# ─── PARSING ──────────────────────────────────────────────────────────────────

def parse_date(s):
    """MM/DD/YYYY → YYYY-MM-DD"""
    try:
        return datetime.strptime(s.strip(), '%m/%d/%Y').strftime('%Y-%m-%d')
    except ValueError:
        return s.strip()


def detect_bank(content):
    """Identify bank from first few lines of CSV."""
    lines = content.lstrip('\ufeff').splitlines()[:15]
    for line in lines[:2]:
        if 'Transaction Date' in line and 'Post Date' in line and 'Category' in line:
            return 'Chase CC'
        if 'Posting Date' in line and 'Details' in line:
            return 'Chase'
    for line in lines:
        if 'Summary Amt.' in line or 'Running Bal.' in line:
            # BofA CardHolder format (cc2/cc3): Summary block + CardHolder Name data header
            if any('CardHolder Name' in l and 'Posting Date' in l for l in lines):
                return 'Bank of America CC'
            return 'Bank of America'
        # BofA credit card alternate export (Posted Date, Reference Number, Payee, Address, Amount)
        if 'Posted Date' in line and 'Reference Number' in line and 'Payee' in line:
            return 'Bank of America CC'
    return 'Unknown'


def parse_chase(content):
    rows = []
    reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
    for row in reader:
        date_str   = row.get('Posting Date', '').strip()
        desc       = row.get('Description', '').strip()
        amt_str    = row.get('Amount', '').replace(',', '').strip()
        tx_type    = row.get('Type', '').strip()
        if not date_str or not desc or not amt_str:
            continue
        try:
            amount = float(amt_str)
        except ValueError:
            continue
        if amount == 0:
            continue
        rows.append({'date': parse_date(date_str), 'description': desc,
                     'amount': amount, 'tx_type': tx_type, 'bank': 'Chase'})
    return rows


def parse_bofa(content):
    rows = []
    lines = content.lstrip('\ufeff').splitlines()

    # Find the transaction header row
    header_idx = None
    for i, line in enumerate(lines):
        if line.strip().startswith('Date,Description,Amount'):
            header_idx = i
            break
    if header_idx is None:
        raise ValueError('Could not find Bank of America transaction header')

    reader = csv.DictReader(lines[header_idx:])
    for row in reader:
        date_str = row.get('Date', '').strip()
        desc     = row.get('Description', '').strip()
        amt_str  = row.get('Amount', '').replace(',', '').replace('"', '').strip()
        if not date_str or not desc or not amt_str:
            continue
        if 'beginning balance' in desc.lower() or 'ending balance' in desc.lower():
            continue
        try:
            amount = float(amt_str)
        except ValueError:
            continue
        if amount == 0:
            continue
        rows.append({'date': parse_date(date_str), 'description': desc,
                     'amount': amount, 'tx_type': '', 'bank': 'Bank of America'})
    return rows


def parse_bofa_cc2(content):
    """Parse BofA CC CSV with CardHolder Name header
       (CardHolder Name, Account/Card Number, Posting Date, Trans. Date,
        Reference ID, Description, Amount, MCC, Merchant Category,
        Transaction Type, Expense Category)
       Also handles the older Payee/Address format as fallback.
    """
    rows  = []
    lines = content.lstrip('\ufeff').splitlines()

    # Find the data header row (CardHolder Name... or Posted Date,Reference Number,Payee...)
    header_idx = None
    for i, line in enumerate(lines):
        if 'CardHolder Name' in line and 'Posting Date' in line:
            header_idx = i
            break
        if 'Posted Date' in line and 'Reference Number' in line and 'Payee' in line:
            header_idx = i
            break
    if header_idx is None:
        raise ValueError('Could not find Bank of America CC transaction header')

    reader = csv.DictReader(lines[header_idx:])
    for row in reader:
        # CardHolder Name format
        date_str = (row.get('Posting Date') or row.get('Posted Date') or '').strip()
        desc     = row.get('Description') or row.get('Payee') or ''
        desc     = desc.strip()
        amt_str  = row.get('Amount', '').replace(',', '').replace('"', '').strip()
        tx_type  = row.get('Transaction Type', '').strip().upper()  # D = debit, C = credit

        if not date_str or not desc or not amt_str:
            continue
        try:
            amount = float(amt_str)
        except ValueError:
            continue
        if amount == 0:
            continue

        # In this format amounts are POSITIVE for purchases — negate so expenses are negative.
        # Credits (payments/refunds) are already negative in the CSV, negating makes them positive.
        amount = -amount

        rows.append({'date': parse_date(date_str), 'description': desc,
                     'amount': amount, 'tx_type': '', 'bank': 'Bank of America CC'})
    return rows


def parse_chase_cc(content):
    """Parse Chase credit card CSV (Transaction Date, Post Date, Description, Category, Type, Amount)."""
    rows = []
    reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')))
    for row in reader:
        date_str = row.get('Transaction Date', '').strip()
        desc     = row.get('Description', '').strip()
        amt_str  = row.get('Amount', '').replace(',', '').strip()
        tx_type  = row.get('Type', '').strip().lower()

        if not date_str or not desc or not amt_str:
            continue
        # Skip payment rows — these already appear in checking as CC payments
        if tx_type == 'payment':
            continue
        try:
            amount = float(amt_str)
        except ValueError:
            continue
        if amount == 0:
            continue

        rows.append({'date': parse_date(date_str), 'description': desc,
                     'amount': amount, 'tx_type': tx_type, 'bank': 'Chase CC'})
    return rows


def parse_csv(content, bank):
    if bank == 'Chase':
        return parse_chase(content)
    if bank == 'Chase CC':
        return parse_chase_cc(content)
    if bank == 'Bank of America':
        return parse_bofa(content)
    if bank == 'Bank of America CC':
        return parse_bofa_cc2(content)
    raise ValueError(f'Unsupported bank: {bank}')


# ─── CATEGORIZATION ───────────────────────────────────────────────────────────

def normalize_description(desc):
    """
    Strip transaction-specific noise (IDs, reference numbers, trailing dates)
    so that two transactions from the same merchant/payee match.
    """
    # Chase Zelle IDs: JPM99xxxxxxxx
    d = re.sub(r'\s+JPM99[A-Z0-9]+', '', desc, flags=re.IGNORECASE)
    # Long numeric IDs (11+ digits)
    d = re.sub(r'\s+\d{11,}', '', d)
    # Trailing date MM/DD
    d = re.sub(r'\s+\d{2}/\d{2}$', '', d)
    # BofA confirmation numbers
    d = re.sub(r'Confirmation#\s*\S+', '', d, flags=re.IGNORECASE)
    d = re.sub(r'transaction#:\s*\S+', '', d, flags=re.IGNORECASE)
    # BofA purchase date suffix e.g. "01/19 PURCHASE"
    d = re.sub(r'\d{2}/\d{2}\s+PURCHASE\s+', ' ', d, flags=re.IGNORECASE)
    # Webull/misc long alphanumeric codes
    d = re.sub(r'\b[A-Z0-9]{10,}\b', '', d)
    # Collapse whitespace
    d = re.sub(r'\s+', ' ', d).strip()
    return d


def auto_categorize(description, amount, tx_type=''):
    """Rule-based categorizer. Returns (category, is_internal)."""
    desc = description.lower()

    # ── Internal transfers ────────────────────────────────────────────────
    internal = [
        'online transfer from sav', 'online transfer to sav',
        'online transfer from chk', 'online transfer to chk',
        'online banking transfer from', 'online banking transfer to',
        'cash redemption',
    ]
    for p in internal:
        if p in desc:
            return 'Internal Transfer', True
    if tx_type == 'ACCT_XFER':
        return 'Internal Transfer', True

    # ── Investments ───────────────────────────────────────────────────────
    if 'webull' in desc or 'wealthfront' in desc:
        if amount > 0:
            # Money returning from investment account is your own capital, not income
            return 'Internal Transfer', True
        else:
            return 'Investment Out', False

    # ── Credit card payments ──────────────────────────────────────────────
    cc = [
        'payment to chase card', 'american express ach pmt',
        'online banking payment to crd', 'bank of america credit card bill payment',
        'mobile banking payment to crd',
    ]
    for p in cc:
        if p in desc:
            return 'Credit Card Payment', False
    if tx_type == 'LOAN_PMT':
        return 'Credit Card Payment', False

    # ── Zelle ─────────────────────────────────────────────────────────────
    if 'zelle payment from' in desc or tx_type in ('QUICKPAY_CREDIT', 'PARTNERFI_TO_CHASE'):
        return 'Zelle In', False
    if 'zelle payment to' in desc or tx_type in ('QUICKPAY_DEBIT', 'CHASE_TO_PARTNERFI'):
        return 'Zelle Out', False

    # ── ATM deposits ──────────────────────────────────────────────────────
    atm_dep = ['atm cash deposit', 'bkofamerica atm', 'bofa fin ctr', 'bkofamerica mobile']
    for p in atm_dep:
        if p in desc and amount > 0:
            return 'ATM Deposit', False
    if tx_type == 'ATM' and amount > 0:
        return 'ATM Deposit', False

    # ── ATM withdrawals ───────────────────────────────────────────────────
    if 'withdrwl' in desc or (tx_type == 'ATM' and amount < 0):
        return 'ATM Withdrawal', False

    # ── Wire transfers ────────────────────────────────────────────────────
    if 'wire type:wire in' in desc or 'wire in' in desc:
        return 'Wire Transfer In', False
    if 'wire type:wire out' in desc or 'wire out' in desc:
        return 'Wire Transfer Out', False

    # ── Tax ───────────────────────────────────────────────────────────────
    if ('irs treas' in desc and 'tax ref' in desc) or 'franchise tax bd' in desc:
        return 'Tax Refund', False
    if 'irs des:usataxpymt' in desc or ('irs' in desc and 'tax' in desc and amount < 0):
        return 'Taxes', False

    # ── Bank fees ─────────────────────────────────────────────────────────
    fees = ['monthly maintenance fee', 'wire transfer fee', 'safebox rental', 'counter check']
    for p in fees:
        if p in desc:
            return 'Bank Fee', False
    if tx_type == 'FEE_TRANSACTION':
        return 'Bank Fee', False

    # ── Cash rewards ──────────────────────────────────────────────────────
    if 'cashreward' in desc or 'cash reward' in desc:
        return 'Cash Rewards', False

    # ── Rent / Mortgage ───────────────────────────────────────────────────
    rent = ['merchant propert', 'new wave lending', 'select portfolio']
    for p in rent:
        if p in desc:
            return 'Rent/Mortgage', False

    # ── Utilities ─────────────────────────────────────────────────────────
    util = ['tmobile', 't-mobile', 'cox comm', 'att*bill']
    for p in util:
        if p in desc:
            return 'Utilities', False

    # ── Insurance ─────────────────────────────────────────────────────────
    if 'transamerica ins' in desc:
        return 'Insurance', False

    # ── Groceries ─────────────────────────────────────────────────────────
    grocery = ['costco', 'northgate', 'sin lee foods', 'el super',
               'wal-mart', 'walmart', 'zion market', 'safeway', 'trader joe',
               'whole foods', 'sprouts', 'vons', 'ralphs', 'kroger']
    for p in grocery:
        if p in desc:
            return 'Groceries', False

    # ── Dining Out ────────────────────────────────────────────────────────
    dining = [
        'doordash', 'uber eats', 'ubereats', 'grubhub', 'postmates',
        'mcdonald', 'burger king', "wendy's", 'wendys', 'taco bell',
        'chipotle', 'subway', 'chick-fil-a', 'chick fil a', 'starbucks',
        'dunkin', 'panda express', 'in-n-out', 'shake shack', 'five guys',
        'popeyes', 'raising cane', 'wingstop', 'jersey mike',
        'panera', 'olive garden', "applebee's", 'ihop', "denny's",
        'cheesecake factory', 'bj\'s restaurant', 'red robin',
        'restaurant', 'sushi', 'ramen', 'pho ', 'boba', 'cafe ',
    ]
    for p in dining:
        if p in desc:
            return 'Dining Out', False

    # ── UCSD / employer income ────────────────────────────────────────────
    if 'uc san diego' in desc or tx_type == 'ACH_CREDIT':
        if amount > 0:
            return 'Income', False

    # ── Default ───────────────────────────────────────────────────────────
    return ('Other Income', False) if amount > 0 else ('Other Expense', False)


def rule_category(conn, description):
    """Return (category, is_internal) from saved rules, or None."""
    rules = conn.execute(
        'SELECT pattern, category FROM category_rules ORDER BY LENGTH(pattern) DESC'
    ).fetchall()
    dl = description.lower()
    for r in rules:
        if r['pattern'].lower() in dl:
            return r['category'], r['category'] == 'Internal Transfer'
    return None


# ─── ROUTES ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload():
    if 'files' not in request.files:
        return jsonify({'error': 'No files'}), 400

    results = []
    for file in request.files.getlist('files'):
        if not file.filename.lower().endswith('.csv'):
            results.append({'file': file.filename, 'error': 'Not a CSV file'})
            continue
        try:
            content = file.read().decode('utf-8-sig', errors='replace')
            bank    = detect_bank(content)
            if bank == 'Unknown':
                results.append({'file': file.filename, 'error': 'Unrecognized CSV format'})
                continue

            txns    = parse_csv(content, bank)
            added   = skipped = 0
            conn    = get_db()

            for tx in txns:
                tx_hash = hashlib.md5(
                    f"{tx['bank']}{tx['date']}{tx['description']}{tx['amount']}".encode()
                ).hexdigest()

                result = rule_category(conn, tx['description'])
                if result:
                    cat, is_int = result
                else:
                    cat, is_int = auto_categorize(
                        tx['description'], tx['amount'], tx.get('tx_type', '')
                    )

                try:
                    conn.execute(
                        '''INSERT INTO transactions
                           (bank, date, description, amount, tx_type, category, is_internal, hash)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                        (tx['bank'], tx['date'], tx['description'], tx['amount'],
                         tx.get('tx_type', ''), cat, 1 if is_int else 0, tx_hash)
                    )
                    added += 1
                except sqlite3.IntegrityError:
                    skipped += 1

            conn.commit()
            conn.close()

            # If a Chase CC was uploaded, hide the matching payment transactions
            # in the Chase checking account to avoid double-counting
            if bank == 'Chase CC':
                conn2 = get_db()
                conn2.execute('''
                    UPDATE transactions
                    SET category = 'Internal Transfer', is_internal = 1
                    WHERE bank = 'Chase' AND is_internal = 0
                    AND (LOWER(description) LIKE '%payment to chase card%'
                         OR tx_type = 'LOAN_PMT')
                ''')
                conn2.commit()
                conn2.close()

            results.append({'file': file.filename, 'bank': bank,
                            'added': added, 'skipped': skipped})
        except Exception as e:
            traceback.print_exc()
            results.append({'file': file.filename, 'error': str(e)})

    return jsonify({'results': results})


def _build_where(bank, start_date, end_date, extra=''):
    where, params = ['1=1'], []
    if extra:
        where.append(extra)
    if bank and bank != 'all':
        where.append('bank = ?');       params.append(bank)
    if start_date:
        where.append('date >= ?');      params.append(start_date)
    if end_date:
        where.append('date <= ?');      params.append(end_date)
    return ' AND '.join(where), params


@app.route('/api/transactions')
def get_transactions():
    bank       = request.args.get('bank', 'all')
    start      = request.args.get('start_date', '')
    end        = request.args.get('end_date', '')
    category   = request.args.get('category', 'all')
    show_int   = request.args.get('show_internal', 'false') == 'true'
    search     = request.args.get('search', '')
    page       = max(1, int(request.args.get('page', 1)))
    per_page   = int(request.args.get('per_page', 50))

    extra = '' if show_int else 'is_internal = 0'
    clause, params = _build_where(bank, start, end, extra)

    if category != 'all':
        clause += ' AND category = ?';  params.append(category)
    if search:
        clause += ' AND (description LIKE ? OR category LIKE ? OR notes LIKE ?)'
        params += [f'%{search}%'] * 3

    sort_col = request.args.get('sort_col', 'date')
    sort_dir = request.args.get('sort_dir', 'desc')
    if sort_col not in ('date', 'amount'): sort_col = 'date'
    if sort_dir not in ('asc', 'desc'):    sort_dir = 'desc'
    order = f'{sort_col} {sort_dir.upper()}, id DESC'

    conn  = get_db()
    total = conn.execute(f'SELECT COUNT(*) FROM transactions WHERE {clause}', params).fetchone()[0]
    rows  = conn.execute(
        f'SELECT * FROM transactions WHERE {clause} ORDER BY {order} LIMIT ? OFFSET ?',
        params + [per_page, (page - 1) * per_page]
    ).fetchall()
    conn.close()

    return jsonify({'transactions': [dict(r) for r in rows],
                    'total': total, 'page': page, 'per_page': per_page})


@app.route('/api/summary')
def get_summary():
    bank  = request.args.get('bank', 'all')
    start = request.args.get('start_date', '')
    end   = request.args.get('end_date', '')

    clause, params = _build_where(bank, start, end,
        "is_internal = 0 AND category NOT IN ('Investment In', 'Investment Out', 'Ignore')")
    conn  = get_db()
    rows  = conn.execute(
        f'''SELECT category, SUM(amount) AS total, COUNT(*) AS count
            FROM transactions WHERE {clause}
            GROUP BY category ORDER BY ABS(SUM(amount)) DESC''',
        params
    ).fetchall()
    conn.close()

    income, expenses, total_in, total_ex = [], [], 0.0, 0.0
    for r in rows:
        entry = {'category': r['category'], 'total': abs(r['total']),
                 'count': r['count'], 'color': CATEGORY_COLORS.get(r['category'], '#999')}
        if r['total'] >= 0:
            income.append(entry);  total_in += r['total']
        else:
            expenses.append(entry); total_ex += abs(r['total'])

    return jsonify({'income': income, 'expenses': expenses,
                    'total_income': total_in, 'total_expenses': total_ex,
                    'net': total_in - total_ex})


@app.route('/api/investments')
def get_investments():
    bank  = request.args.get('bank', 'all')
    start = request.args.get('start_date', '')
    end   = request.args.get('end_date', '')

    extra  = "(LOWER(description) LIKE '%webull%' OR LOWER(description) LIKE '%wealthfront%')"
    clause, params = _build_where(bank, start, end, extra)

    conn = get_db()
    rows = conn.execute(
        f'SELECT * FROM transactions WHERE {clause} ORDER BY date DESC', params
    ).fetchall()
    conn.close()

    # Money sent TO investment accounts (negative in checking)
    deposited = sum(abs(r['amount']) for r in rows if r['amount'] < 0)
    # Money returned FROM investment accounts (positive in checking)
    withdrawn = sum(r['amount'] for r in rows if r['amount'] > 0)

    platforms = []
    descs = [r['description'].lower() for r in rows]
    if any('webull' in d for d in descs):      platforms.append('Webull')
    if any('wealthfront' in d for d in descs): platforms.append('Wealthfront')

    return jsonify({
        'deposited':  deposited,
        'withdrawn':  withdrawn,
        'net':        deposited - withdrawn,   # net still invested (positive = more in than out)
        'count':      len(rows),
        'platforms':  platforms,
    })


@app.route('/api/transaction/<int:tx_id>', methods=['PUT'])
def update_transaction(tx_id):
    data   = request.get_json()
    fields = {k: data[k] for k in ('category', 'notes', 'is_internal') if k in data}
    if not fields:
        return jsonify({'error': 'Nothing to update'}), 400
    sets   = ', '.join(f'{k} = ?' for k in fields)
    conn   = get_db()
    conn.execute(f'UPDATE transactions SET {sets} WHERE id = ?',
                 list(fields.values()) + [tx_id])
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/similar/<int:tx_id>')
def get_similar(tx_id):
    conn = get_db()
    tx   = conn.execute('SELECT * FROM transactions WHERE id = ?', (tx_id,)).fetchone()
    if not tx:
        conn.close()
        return jsonify({'error': 'Not found'}), 404

    norm    = normalize_description(tx['description'])
    others  = conn.execute('SELECT * FROM transactions WHERE id != ?', (tx_id,)).fetchall()
    conn.close()

    similar = [dict(r) for r in others if normalize_description(r['description']) == norm]
    return jsonify({'similar': similar, 'pattern': norm, 'current': dict(tx)})


@app.route('/api/mass-categorize', methods=['POST'])
def mass_categorize():
    data     = request.get_json()
    ids      = data.get('transaction_ids', [])
    category = data.get('category', '')
    pattern  = data.get('pattern', '')
    save     = data.get('save_rule', True)

    if not ids or not category:
        return jsonify({'error': 'transaction_ids and category required'}), 400

    conn = get_db()
    ph   = ','.join('?' * len(ids))
    conn.execute(f'UPDATE transactions SET category = ? WHERE id IN ({ph})',
                 [category] + ids)
    if save and pattern:
        conn.execute('INSERT OR REPLACE INTO category_rules (pattern, category) VALUES (?, ?)',
                     (pattern.lower(), category))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'updated': len(ids)})


@app.route('/api/banks')
def get_banks():
    conn = get_db()
    rows = conn.execute(
        'SELECT bank, COUNT(*) AS count, MIN(date) AS from_date, MAX(date) AS to_date '
        'FROM transactions GROUP BY bank'
    ).fetchall()
    conn.close()
    return jsonify({'banks': [dict(r) for r in rows]})


@app.route('/api/banks/<path:bank_name>', methods=['DELETE'])
def delete_bank(bank_name):
    conn = get_db()
    conn.execute('DELETE FROM transactions WHERE bank = ?', (bank_name,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/categories')
def get_categories():
    return jsonify({'income': INCOME_CATEGORIES, 'expense': EXPENSE_CATEGORIES,
                    'special': SPECIAL_CATEGORIES,
                    'all': ALL_CATEGORIES, 'colors': CATEGORY_COLORS})


@app.route('/api/rules')
def get_rules():
    conn = get_db()
    rows = conn.execute('SELECT * FROM category_rules ORDER BY created_at DESC').fetchall()
    conn.close()
    return jsonify({'rules': [dict(r) for r in rows]})


@app.route('/api/rules/<int:rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    conn = get_db()
    conn.execute('DELETE FROM category_rules WHERE id = ?', (rule_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/date-range')
def date_range():
    conn = get_db()
    row  = conn.execute('SELECT MIN(date) AS mn, MAX(date) AS mx FROM transactions').fetchone()
    conn.close()
    return jsonify({'min': row['mn'], 'max': row['mx']})

@app.route('/api/bar-trends')
def get_bar_trends():
    bank        = request.args.get('bank', 'all')
    start       = request.args.get('start_date', '')
    end         = request.args.get('end_date', '')
    granularity = request.args.get('granularity', 'monthly')
    category    = request.args.get('category', 'all')

    if granularity == 'daily':
        period_expr = "date"
    elif granularity == 'weekly':
        period_expr = "strftime('%Y-W%W', date)"
    elif granularity == 'quarterly':
        period_expr = ("strftime('%Y', date) || '-Q' || "
                       "((CAST(strftime('%m', date) AS INTEGER) - 1) / 3 + 1)")
    else:
        period_expr = "strftime('%Y-%m', date)"

    excl = "is_internal = 0 AND category NOT IN ('Investment In', 'Investment Out', 'Ignore')"
    clause, params = _build_where(bank, start, end, excl)

    cat_clause, cat_params = clause, list(params)
    if category != 'all':
        cat_clause += ' AND category = ?'
        cat_params.append(category)

    conn = get_db()

    # Per-category per-period (expenses, for stacked view)
    exp_rows = conn.execute(f'''
        SELECT {period_expr} AS period, category,
               ROUND(SUM(ABS(amount)), 2) AS total
        FROM transactions
        WHERE {cat_clause} AND amount < 0
        GROUP BY period, category
        ORDER BY period
    ''', cat_params).fetchall()

    # Per-period income vs expenses totals
    vs_rows = conn.execute(f'''
        SELECT {period_expr} AS period,
               ROUND(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 2) AS income,
               ROUND(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 2) AS expenses
        FROM transactions
        WHERE {cat_clause}
        GROUP BY period
        ORDER BY period
    ''', cat_params).fetchall()

    conn.close()

    # Build stacked structure: {category: {period: total}}
    periods = sorted(set(r['period'] for r in exp_rows) | set(r['period'] for r in vs_rows))
    cat_map = {}
    for r in exp_rows:
        cat_map.setdefault(r['category'], {})[r['period']] = r['total']

    by_category = {cat: [cat_map[cat].get(p, 0) for p in periods]
                   for cat in cat_map}

    vs_map = {r['period']: {'income': r['income'], 'expenses': r['expenses']}
              for r in vs_rows}

    return jsonify({
        'periods':      periods,
        'by_category':  by_category,
        'income':       [vs_map.get(p, {}).get('income', 0)   for p in periods],
        'expenses':     [vs_map.get(p, {}).get('expenses', 0) for p in periods],
    })


@app.route('/api/trends')
def get_trends():
    bank        = request.args.get('bank', 'all')
    start       = request.args.get('start_date', '')
    end         = request.args.get('end_date', '')
    granularity = request.args.get('granularity', 'monthly')

    if granularity == 'daily':
        period_expr = "date"
    elif granularity == 'weekly':
        period_expr = "strftime('%Y-W%W', date)"
    elif granularity == 'quarterly':
        period_expr = ("strftime('%Y', date) || '-Q' || "
                       "((CAST(strftime('%m', date) AS INTEGER) - 1) / 3 + 1)")
    else:
        period_expr = "strftime('%Y-%m', date)"

    clause, params = _build_where(bank, start, end,
        "is_internal = 0 AND category NOT IN ('Investment In', 'Investment Out', 'Ignore')")

    conn = get_db()
    rows = conn.execute(f'''
        SELECT {period_expr} AS period,
               ROUND(SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END), 2) AS income,
               ROUND(SUM(CASE WHEN amount < 0 THEN ABS(amount) ELSE 0 END), 2) AS expenses
        FROM transactions
        WHERE {clause}
        GROUP BY period
        ORDER BY period
    ''', params).fetchall()
    conn.close()

    return jsonify({
        'periods':  [r['period']   for r in rows],
        'income':   [r['income']   for r in rows],
        'expenses': [r['expenses'] for r in rows],
    })


# ─── RUN ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    print('\n  Finance Dashboard running at http://localhost:5000\n')
    app.run(debug=True, port=5000)
