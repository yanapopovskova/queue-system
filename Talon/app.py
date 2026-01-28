# app.py
from flask import Flask, render_template, request, jsonify, redirect, url_for
import config
from datetime import datetime
from datetime import datetime


app = Flask(__name__)

def generate_ticket_number(client_id, first_name, last_name):
    day = datetime.now().day
    first_initial = first_name[0].lower() if first_name else 'x'
    last_initial = last_name[0].lower() if last_name else 'x'
    return f"{client_id}{first_initial}{last_initial}{day}"

# --- Главная страница: выдача талонов ---
@app.route('/')
def index():
    conn = config.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id_услуга, название_услуги FROM Услуга")
    services = cursor.fetchall()
    conn.close()
    return render_template('index.html', services=services)

# --- Выдача талона ---
@app.route('/issue-ticket', methods=['POST'])
def issue_ticket():
    service_id = request.form['service_id']
    first_name = request.form['first_name'].strip()
    last_name = request.form['last_name'].strip()
    phone = request.form.get('phone', '').strip() or None

    conn = config.get_db_connection()
    cursor = conn.cursor()

    # Поиск клиента
    cursor.execute("""
        SELECT id_клиент FROM Клиент 
        WHERE имя = ? AND фамилия = ? AND номер_телефона = ?
    """, (first_name, last_name, phone))
    client = cursor.fetchone()

    if not client:
        cursor.execute("""
            INSERT INTO Клиент (имя, фамилия, номер_телефона)
            OUTPUT INSERTED.id_клиент
            VALUES (?, ?, ?)
        """, (first_name, last_name, phone))
        client_id = cursor.fetchone()[0]
        conn.commit()
    else:
        client_id = client[0]

    # Получаем название услуги
    cursor.execute("SELECT название_услуги FROM Услуга WHERE id_услуга = ?", (service_id,))
    service_name = cursor.fetchone()[0]

    # Создаём талон
    cursor.execute("""
        INSERT INTO Талон (тип_услуги, id_клиент)
        VALUES (?, ?)
    """, (service_name, client_id))
    conn.commit()
    conn.close()

    # Генерируем номер талона
    ticket_number = generate_ticket_number(client_id, first_name, last_name)

    # Передаём на страницу подтверждения
    return render_template('ticket_issued.html', ticket_number=ticket_number, service=service_name)

# --- Табло: текущий номер ---
@app.route('/display')
def display():
    return render_template('display.html')

@app.route('/api/current-ticket')
def current_ticket():
    conn = config.get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT TOP 1 
            t.id_талон,
            t.тип_услуги,
            c.id_клиент,
            c.имя,
            c.фамилия
        FROM Талон t
        JOIN Клиент c ON t.id_клиент = c.id_клиент
        WHERE t.время_вызова_клиента IS NOT NULL 
          AND t.время_начала_обслуживания IS NULL
        ORDER BY t.время_вызова_клиента ASC
    """)
    row = cursor.fetchone()
    conn.close()

    if row:
        client_id, first_name, last_name = row[2], row[3], row[4]
        ticket_number = generate_ticket_number(client_id, first_name, last_name)
        return jsonify({
            'ticket_number': ticket_number,
            'service': row[1]
        })
    else:
        return jsonify({'ticket_number': '--', 'service': ''})

# --- Админ-панель ---
@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/api/start-service')
def start_service():
    conn = config.get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()

    # Найти вызванного, но ещё не начавшего клиента
    cursor.execute("""
        SELECT TOP 1 id_талон 
        FROM Талон 
        WHERE время_вызова_клиента IS NOT NULL 
          AND время_начала_обслуживания IS NULL
        ORDER BY время_вызова_клиента ASC
    """)
    ticket = cursor.fetchone()

    if ticket:
        cursor.execute("""
            UPDATE Талон 
            SET время_начала_обслуживания = ? 
            WHERE id_талон = ?
        """, (now, ticket[0]))
        conn.commit()

    conn.close()
    return '', 204

@app.route('/api/next')
def next_ticket():
    conn = config.get_db_connection()
    cursor = conn.cursor()
    now = datetime.now()

    # 1. Найти текущего вызванного клиента (который ещё не начал или уже начал, но не завершил)
    cursor.execute("""
        SELECT id_талон 
        FROM Талон 
        WHERE время_вызова_клиента IS NOT NULL 
          AND время_окончания_обслуживания IS NULL
        ORDER BY время_вызова_клиента ASC
    """)
    current = cursor.fetchone()

    # 2. Если такой есть — завершить его обслуживание
    if current:
        cursor.execute("""
            UPDATE Талон 
            SET время_окончания_обслуживания = ? 
            WHERE id_талон = ?
        """, (now, current[0]))

    # 3. Найти следующего в очереди (ещё не вызванного)
    cursor.execute("""
        SELECT TOP 1 id_талон 
        FROM Талон 
        WHERE время_вызова_клиента IS NULL
        ORDER BY время_создания_талона ASC
    """)
    next_ticket_row = cursor.fetchone()

    if next_ticket_row:
        # Вызвать следующего
        cursor.execute("""
            UPDATE Талон 
            SET время_вызова_клиента = ? 
            WHERE id_талон = ?
        """, (now, next_ticket_row[0]))

    conn.commit()
    conn.close()
    return '', 204
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)