from flask import Flask, render_template, request, make_response, redirect, url_for, session, flash, jsonify, g
from flask_cors import CORS
import psycopg2
from psycopg2 import Error
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import bcrypt
import json 
import random
import requests

app = Flask(__name__)
CORS(app)
app.secret_key = 'your_secret_key'


@app.after_request
def apply_csp(response):
    response.headers['Content-Security-Policy'] = (
        "connect-src 'self' http://localhost:5055"
    )
    return response

def connect_db():
    return psycopg2.connect(
        user="postgres",
        password="vasilica",
        host="192.168.16.164",
        port="5432",
        database="postgres"
    )

#----------------------------------------DECORATORS----------------------------------------

# Authentication decorator
def authenticate(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))

        user = get_user(session['username'])
        competitor = get_competitor(session['username'])
        
        if not user and not competitor:
            return jsonify({'message': 'Utilizatorul nu are permisiunea necesară pentru acces.'}), 403
        
        return f(*args, **kwargs)
    
    return decorated

# Role-based access control decorator
def authorize(role):  # Define a function to create a decorator for role-based access control
    def wrapper(f):  # Define a nested function that takes a function 'f' as an argument
        @wraps(f)  # Use the wraps decorator to preserve the metadata of the decorated function 'f'
        def decorated(*args, **kwargs):  # Define a nested function 'decorated' that will replace the original function 'f'
            if session['user_type'] != role:  # Check if the user's role stored in the session doesn't match the required role
                return jsonify({'message': 'Permisiune refuzată!'}), 403  # If the user's role doesn't match, return a JSON response with the message 'Permission denied!' and a 403 Forbidden status code
            return f(*args, **kwargs)  # If the user's role matches, call the original function 'f' with the provided arguments and return its result
        return decorated  # Return the nested 'decorated' function
    return wrapper  # Return the nested 'wrapper' function



#----------------------------------------FUNCTIONS----------------------------------------

# Check credentials function (verify in database)
def check_credentials(username, password):
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()
        
        # Check if the user exists in 'users' table
        cursor.execute("SELECT username, password, user_type FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        if not user:
            # If user does not exist in 'users' table, check 'concurenti' table
            cursor.execute("SELECT username, password FROM concurenti WHERE username = %s", (username,))
            concurent = cursor.fetchone()
            if concurent:
                user = (concurent[0], concurent[1], 'concurent')
        
        return user  # Returns (username, hashed_password, user_type) if user exists, else None
    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea credențialelor utilizatorului:", error)
        return None
    finally:
        if connection:
            cursor.close()
            connection.close()

def get_user(username):
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()
        
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        
        return user
        
    except (Exception, Error) as error:
        print("Eroare la preluarea utilizatorului:", error)
        return None
        
    finally:
        if connection:
            cursor.close()
            connection.close()

def get_competitor(username):
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()
        
        cursor.execute("SELECT * FROM concurenti WHERE username = %s", (username,))
        competitor = cursor.fetchone()
        
        return competitor
        
    except (Exception, Error) as error:
        print("Eroare la preluarea concurentului:", error)
        return None
        
    finally:
        if connection:
            cursor.close()
            connection.close()


#----------------------------------------ROUTES----------------------------------------
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = check_credentials(username, password)

        if user:
            stored_password = user[1]
            if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                session['username'] = user[0]
                session['user_type'] = user[2]
                g.current_user = {'username': user[0], 'user_type': user[2]}
                print("Sesiune dupa login:", session)

                response = make_response(jsonify({"message": "ok"}))
                return response
        flash("Utilizatorul sau parola au fost introduse greșit.", "danger")
        return redirect(url_for('login'))

    return render_template('login.html')




@app.route('/register', methods=['GET', 'POST'])
def register():
    username = session['username']  
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_type = request.form['user_type']
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()
            cursor.execute("INSERT INTO users (username, password, user_type) VALUES (%s, %s, %s)",
                           (username, hashed_password.decode('utf-8'), user_type))
            connection.commit()
            flash(f"Utilizator înregistrat cu succes!", "success")
            return redirect(url_for('view_users'))
        except (Exception, Error) as error:
            print("Eroare la înregistrare:", error)
            flash(f"A apărut o eroare la înregistrare: {error}", "danger")
            return redirect(url_for('register'))
        finally:
            if connection:
                cursor.close()
                connection.close()
    return render_template('register.html', username=username)



@app.route('/register_contestant', methods=['GET', 'POST'])
def register_contestant():
    username = session['username']  
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_type = request.form['user_type']
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()
            cursor.execute("INSERT INTO concurenti (username, password, user_type) VALUES (%s, %s, %s)",
                           (username, hashed_password.decode('utf-8'), user_type))
            connection.commit()
            flash(f"Concurent înregistrat cu succes!", "success")
            return redirect(url_for('view_contestants'))
        except (Exception, Error) as error:
            print("Eroare la înregistrare:", error)
            flash(f"A apărut o eroare la înregistrare:{error}", "danger")
            return redirect(url_for('register_contestant'))
        finally:
            if connection:
                cursor.close()
                connection.close()
    return render_template('register_contestant.html',username=username)


@app.route('/view_contestants', methods=['GET', 'POST'])
@authenticate
def view_contestants():
    username = session['username']
    user_type = session['user_type']
    contestants = []
    search_query = request.args.get('query', '').lower()
    column = request.args.get('column', 'username')
    order = request.args.get('order', 'asc')

    column_mapping = {
        'id': 'c.id',
        'username': 'c.username',
        'user_type': 'c.user_type',
        'contests_assigned': 'contests_assigned'
    }

    if column not in column_mapping:
        column = 'username'

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        query = """
            SELECT c.id, c.username, c.user_type, array_agg(pc.id_concurs) AS assigned_contests, array_agg(concurs.titlu) AS contest_titles
            FROM concurenti c
            LEFT JOIN participanti_concurs pc ON c.username = pc.username
            LEFT JOIN concurs ON pc.id_concurs = concurs.id_concurs
        """

        if search_query:
            query += """
                WHERE LOWER(c.username) LIKE %s 
                OR LOWER(concurs.titlu) LIKE %s
                OR CAST(c.id AS TEXT) LIKE %s
            """
            search_param = f"%{search_query}%"
            cursor.execute(query + " GROUP BY c.id, c.username, c.user_type", (search_param, search_param, search_param))
        else:
            cursor.execute(query + " GROUP BY c.id, c.username, c.user_type")

        contestants = cursor.fetchall()

    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea datelor din PostgreSQL:", error)
    finally:
        if connection:
            cursor.close()
            connection.close()

    contestants_data = []
    for contestant in contestants:
        contests_assigned = []
        if contestant[3] and contestant[4]:  # Check if there are assigned contests
            for i in range(len(contestant[3])):
                contests_assigned.append({
                    'id': contestant[3][i],
                    'titlu': contestant[4][i]
                })

        contestants_data.append({
            'id': contestant[0],
            'username': contestant[1],
            'user_type': contestant[2],
            'contests_assigned': contests_assigned
        })

    # Sorting logic
    reverse_order = (order == 'desc')
    if column == 'contests_assigned':
        contestants_data.sort(key=lambda x: len(x['contests_assigned']), reverse=reverse_order)
    else:
        contestants_data.sort(key=lambda x: x[column], reverse=reverse_order)

    has_contestants = len(contestants_data) > 0

    return render_template(
        'view_contestants.html',
        username=username,
        user_type=user_type,
        contestants=contestants_data,
        has_contestants=has_contestants,
        column=column,
        order=order
    )






@app.route('/edit_contestant/<int:id>', methods=['GET', 'POST'])
def edit_contestant(id):
    conn = None
    cursor = None
    username=session['username']
    try:
        if request.method == 'POST':
            old_username = request.form.get('old_username')
            new_username = request.form.get('username')
            password = request.form.get('password')
            user_type = "contestant" 
            selected_contests = request.form.getlist('contests')

            if not new_username:
                flash("Username-ul este obligatoriu!", "danger")
                return redirect(url_for('edit_contestant', id=id))

            conn = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = conn.cursor()

            cursor.execute("BEGIN;")

            cursor.execute("DELETE FROM participanti_concurs WHERE username = %s", (old_username,))
            cursor.execute("DELETE FROM participanti_raspuns WHERE username = %s", (old_username,))
            cursor.execute("DELETE FROM participanti_scoruri WHERE username = %s", (old_username,))

            if password:
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                cursor.execute("""
                    UPDATE concurenti
                    SET username = %s, password = %s, user_type = %s
                    WHERE id = %s
                """, (new_username, hashed_password.decode('utf-8'), user_type, id))
            else:
                cursor.execute("""
                    UPDATE concurenti
                    SET username = %s, user_type = %s
                    WHERE id = %s
                """, (new_username, user_type, id))

            for contest_id in selected_contests:
                cursor.execute("""
                    INSERT INTO participanti_concurs (id_concurs, username)
                    VALUES (%s, %s)
                """, (contest_id, new_username))

            conn.commit()

            flash('Concurentul a fost actualizat cu succes!', 'success')
            return redirect(url_for('view_contestants'))

        else:
            conn = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = conn.cursor()

            cursor.execute("SELECT id, username, user_type FROM concurenti WHERE id = %s", (id,))
            contestant = cursor.fetchone()

            if not contestant:
                flash('Concurentul nu a fost găsit!', 'danger')
                return redirect(url_for('view_contestants'))

            cursor.execute("SELECT id_concurs, titlu FROM concurs")
            contests = cursor.fetchall()

            cursor.execute("SELECT id_concurs FROM participanti_concurs WHERE username = %s", (contestant[1],))
            assigned_contests = [row[0] for row in cursor.fetchall()]

            return render_template('edit_contestant.html', contestant=contestant, contests=contests, assigned_contests=assigned_contests, username=username)

    except (Exception, psycopg2.Error) as error:
        if conn:
            conn.rollback()  
        print("Eroare la actualizarea concurentului:", error)
        flash(f"A intervenit o eroare în timpul actualizării concurentului: {error}", 'danger')
        return redirect(url_for('edit_contestant', id=id))
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()




@app.route('/delete_contestant/<int:id>')
def delete_contestant(id):
    try:
        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute("SELECT username FROM concurenti WHERE id = %s", (id,))
        username = cursor.fetchone()

        if username:
            username = username[0]

            cursor.execute("DELETE FROM participanti_raspuns WHERE username = %s", (username,))
            cursor.execute("DELETE FROM participanti_concurs WHERE username = %s", (username,))
            cursor.execute("DELETE FROM participanti_scoruri WHERE username = %s", (username,))

            cursor.execute("DELETE FROM concurenti WHERE id = %s", (id,))

            connection.commit()
            flash(f"Concurentul a fost șters cu succes!", "success")
        else:
            flash(f"Concurentul nu a fost găsit.", "danger")

    except (Exception, psycopg2.Error) as error:
        print("Eroare la ștergere:", error)
        connection.rollback() 
        flash(f"A apărut o eroare în timpul ștergerii: {error}", "danger")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for('view_contestants'))



@app.route('/menu')
def menu():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user_type = session['user_type']
    
    assigned_contests = []
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()
        
        if user_type == 'concurent':
            cursor.execute("""
                SELECT DISTINCT pc.id_concurs, c.titlu 
                FROM participanti_concurs pc
                JOIN concurs c ON pc.id_concurs = c.id_concurs
                WHERE pc.username = %s
            """, (username,))
            assigned_contests = cursor.fetchall()

            if not assigned_contests:
                flash(f"Nu sunteți asignat la niciun concurs.", "danger")
    
    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea concursurilor atribuite:", error)
        flash(f"A intervenit o eroare în timpul preluării concursurilor atribuite: {error}", "danger")
    
    finally:
        if connection:
            cursor.close()
            connection.close()

    return render_template('menu.html', username=username, user_type=user_type, assigned_contests=assigned_contests)





@app.route('/logout')
def logout():
    session.pop('username', None)  
    session.pop('user_type', None)
    g.current_user = None 
    return redirect(url_for('login'))



@app.route('/view_contests', methods=['GET', 'POST'])
@authenticate
def view_contests():
    username = session['username']
    user_type = session['user_type']
    contests = []
    search_query = request.args.get('query', '').lower()
    column = request.args.get('column', 'data_ora')
    order = request.args.get('order', 'asc')

    column_mapping = {
        'id_concurs': 'c.id_concurs',
        'titlu': 'c.titlu',
        'sucursala': 'c.sucursala',
        'departament': 'c.departament',
        'data_ora': 'c.data_ora',
        'participants': 'participant_count',
        'nume_set': 's.nume_set'  # Updated to reflect the new field
    }

    if column not in column_mapping:
        column = 'data_ora'

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        # Update SQL query
        query = """
            SELECT c.id_concurs, c.titlu, c.sucursala, c.departament, c.data_ora, 
                   ARRAY_AGG(p.username) AS participants, 
                   COUNT(p.username) AS participant_count, 
                   s.nume_set
            FROM concurs c
            LEFT JOIN participanti_concurs p ON c.id_concurs = p.id_concurs
            LEFT JOIN concursuri_seturi cs ON c.id_concurs = cs.id_concurs
            LEFT JOIN seturi_intrebari s ON cs.id_set = s.id_set
        """

        if search_query:
            query += """
                WHERE LOWER(c.titlu) LIKE %s
                OR LOWER(c.sucursala) LIKE %s
                OR LOWER(c.departament) LIKE %s
                OR EXISTS (
                    SELECT 1
                    FROM participanti_concurs pc
                    WHERE pc.id_concurs = c.id_concurs
                    AND LOWER(pc.username) LIKE %s
                )
            """
            search_param = f"%{search_query}%"
            params = [search_param, search_param, search_param, search_param]
        else:
            params = []

        query += f" GROUP BY c.id_concurs, s.nume_set ORDER BY {column_mapping[column]} {'ASC' if order == 'asc' else 'DESC'}"
        cursor.execute(query, tuple(params))
        contests = cursor.fetchall()

    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea datelor din PostgreSQL", error)
    finally:
        if connection:
            cursor.close()
            connection.close()

    contests_data = []
    for contest in contests:
        contests_data.append({
            'id_concurs': contest[0],
            'titlu': contest[1],
            'sucursala': contest[2],
            'departament': contest[3],
            'data_ora': contest[4],
            'participants': contest[5],
            'nume_set': contest[7]
        })

    has_contests = len(contests_data) > 0

    return render_template(
        'view_contests.html',
        username=username,
        user_type=user_type,
        contests=contests_data,
        has_contests=has_contests,
        column=column,
        order=order
    )



@app.route('/create_question_set', methods=['GET', 'POST'])
@authenticate
@authorize('admin')
def create_question_set():
    username = session['username']
    
    if request.method == 'POST':
        id_set = request.form.get('id_set')
        nume_set = request.form.get('nume_set')
        

        if not id_set or not nume_set:
            flash(f"Toate câmpurile sunt obligatorii.", "danger")
            return redirect(url_for('create_question_set'))

        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            # Check if the id_set already exists
            cursor.execute("SELECT id_set FROM seturi_intrebari WHERE id_set = %s", (id_set,))
            existing_id = cursor.fetchone()
            if existing_id:
                flash(f"ID-ul setului de întrebări există deja! Te rugăm să alegi altul.", "danger")
                return redirect(url_for('create_question_set'))

            # Insert the new question set
            cursor.execute("""
                INSERT INTO seturi_intrebari (id_set, nume_set)
                VALUES (%s, %s)
            """, (id_set, nume_set))

            for i in range(18):  # Iterate through 18 questions
                question_text = request.form.get(f'questions[{i}][question]')
                answer_count = int(request.form.get(f'questions[{i}][answer_count]'))
                
                if not question_text:
                    continue  # Skip empty questions
                
                # Insert question
                cursor.execute("""
                    INSERT INTO intrebari (id_set, intrebare, is_used)
                    VALUES (%s, %s, %s)
                    RETURNING id_intrebare
                """, (id_set, question_text, False))
                id_intrebare = cursor.fetchone()[0]

                # Insert answers
                for j in range(answer_count):
                    raspuns = request.form.get(f'questions[{i}][answers][{j}][answer]')
                    punctaj = int(request.form.get(f'questions[{i}][answers][{j}][score]'))
                    
                    if raspuns:
                        cursor.execute("""
                            INSERT INTO raspunsuri (id_intrebare, raspuns, punctaj)
                            VALUES (%s, %s, %s)
                        """, (id_intrebare, raspuns, punctaj))

            connection.commit()
            return redirect(url_for('view_question_sets'))

        except (Exception, psycopg2.Error) as error:
            print("Eroare la crearea setului de întrebări:", error)
            flash(f"A intervenit o eroare în timpul creării setului de întrebări: {error}", "danger")
            return redirect(url_for('create_question_set'))

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    contests = get_contests()  

    return render_template('create_question_set.html', question_set={}, contests=contests, username=username)



def get_contests():
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()
        cursor.execute("SELECT id_concurs, titlu FROM concurs ORDER BY id_concurs ASC")
        contests = cursor.fetchall()
        return contests
    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea concursurilor:", error)
        return []
    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



@app.route('/create_contest', methods=['GET', 'POST'])
def create_contest():
    username = session.get('username')

    if request.method == 'POST':
        id_concurs = request.form.get('id_concurs')
        title = request.form.get('title')
        branch = request.form.get('branch')
        department = request.form.get('department')
        datetime = request.form.get('datetime')
        participants = request.form.getlist('participants')
        id_set = request.form.get('id_set')

        if not all([id_concurs, title, branch, department, datetime, id_set]):
            flash("Toate câmpurile sunt obligatorii.", "danger")
            return redirect(url_for('create_contest'))

        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            # Verificăm dacă ID-ul concursului există deja
            cursor.execute("SELECT id_concurs FROM concurs WHERE id_concurs = %s", (id_concurs,))
            existing_id = cursor.fetchone()
            
            if existing_id:
                flash("ID-ul concursului există deja! Te rugăm să alegi altul.", "danger")
                return redirect(url_for('create_contest'))
            
            # Obținem întrebările disponibile
            cursor.execute("""
                SELECT id_intrebare FROM intrebari
                WHERE id_set = %s
                ORDER BY random()
            """, (id_set,))
            available_questions = cursor.fetchall()

            # Verificăm dacă avem suficiente întrebări
            if len(available_questions) < 6:  # Ajustăm la 6 întrebări pentru quiz
                flash("Setul de întrebări nu are suficiente întrebări disponibile (minim 6).", "danger")
                return redirect(url_for('create_contest'))

            # Alegem întrebările pentru quiz 1 și quiz 2
            quiz1_questions = available_questions[:3]
            quiz2_questions = available_questions[3:6]

            # Inserăm concursul în baza de date
            cursor.execute("""
                INSERT INTO concurs (id_concurs, titlu, sucursala, departament, data_ora)
                VALUES (%s, %s, %s, %s, %s)
            """, (id_concurs, title, branch, department, datetime))

            # Inserăm participanții
            for participant in participants:
                cursor.execute("""
                    INSERT INTO participanti_concurs (id_concurs, username)
                    VALUES (%s, %s)
                """, (id_concurs, participant))

            # Inserăm chestionarele
            cursor.execute("""
                INSERT INTO chestionare (id_concurs, numar_chestionar, tip, id_set)
                VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
            """, (id_concurs, 1, 'standard', id_set, id_concurs, 2, 'rezerva', id_set))

            # Obținem ID-urile chestionarelor create
            cursor.execute("""
                SELECT id_chestionar, tip FROM chestionare
                WHERE id_concurs = %s
            """, (id_concurs,))
            quiz_ids = cursor.fetchall()
            quiz1_id = next(id for id, tip in quiz_ids if tip == 'standard')
            quiz2_id = next(id for id, tip in quiz_ids if tip == 'rezerva')

            # Inserăm întrebările în chestionare
            for question_id in quiz1_questions:
                cursor.execute("""
                    INSERT INTO chestionar_intrebari (id_chestionar, id_intrebare)
                    VALUES (%s, %s)
                """, (quiz1_id, question_id[0]))

            for question_id in quiz2_questions:
                cursor.execute("""
                    INSERT INTO chestionar_intrebari (id_chestionar, id_intrebare)
                    VALUES (%s, %s)
                """, (quiz2_id, question_id[0]))

            # Marcăm întrebările utilizate
            cursor.execute("""
                UPDATE intrebari
                SET is_used = TRUE
                WHERE id_intrebare IN %s
            """, (tuple([q[0] for q in quiz1_questions + quiz2_questions]),))

            # Resetăm întrebările dacă toate au fost utilizate
            cursor.execute("""
                SELECT COUNT(*) FROM intrebari WHERE id_set = %s AND is_used = FALSE
            """, (id_set,))
            remaining_questions = cursor.fetchone()[0]

            if remaining_questions == 0:
                cursor.execute("""
                    UPDATE intrebari
                    SET is_used = FALSE
                    WHERE id_set = %s
                """, (id_set,))

            # Asociem concursul cu setul de întrebări
            cursor.execute("""
                INSERT INTO concursuri_seturi (id_concurs, id_set)
                VALUES (%s, %s)
                ON CONFLICT (id_concurs, id_set) DO UPDATE
                SET id_set = EXCLUDED.id_set
            """, (id_concurs, id_set))

            connection.commit()

            return redirect(url_for('view_contests'))

        except (Exception, psycopg2.Error) as error:
            print("Eroare la crearea concursului:", error)
            flash(f"A intervenit o eroare în timpul creării concursului: {error}", "danger")
            return redirect(url_for('create_contest'))
        
        finally:
            if connection:
                cursor.close()
                connection.close()

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        cursor.execute("SELECT DISTINCT sucursala FROM organizare")
        branches = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT sucursala, departament FROM organizare")
        organizare = cursor.fetchall()

        cursor.execute("SELECT username FROM concurenti ORDER BY username ASC")
        participants = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT id_set, nume_set FROM seturi_intrebari")
        question_sets = cursor.fetchall()

    except (Exception, psycopg2.Error) as error:
        print("Eroare la accesarea bazei de date:", error)
        flash(f"A intervenit o eroare în timpul accesării bazei de date: {error}", "danger")
        return redirect(url_for('create_contest'))
    
    finally:
        if connection:
            cursor.close()
            connection.close()

    return render_template(
        'create_contest.html',
        username=username,
        branches=branches,
        organizare=organizare,
        participants=participants,
        question_sets=question_sets
    )




@app.route('/preview_quizzes/<id_concurs>', methods=['GET'])

def preview_quizzes(id_concurs):
    username = session.get('username')
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        # Fetch quizzes for the contest
        cursor.execute("""
            SELECT numar_chestionar, tip FROM chestionare
            WHERE id_concurs = %s
        """, (id_concurs,))
        quizzes = cursor.fetchall()

        # Initialize quiz data
        quiz_data = {}
        for numar_chestionar, tip in quizzes:
            # Fetch questions for each quiz
            cursor.execute("""
                SELECT id_intrebare, intrebare FROM intrebari
                WHERE id_intrebare IN (
                    SELECT id_intrebare FROM chestionar_intrebari
                    WHERE id_chestionar = (
                        SELECT id_chestionar FROM chestionare
                        WHERE id_concurs = %s AND numar_chestionar = %s
                    )
                )
            """, (id_concurs, numar_chestionar))
            questions = cursor.fetchall()

            # Fetch answers for each question
            questions_with_answers = []
            for id_intrebare, intrebare in questions:
                cursor.execute("""
                    SELECT raspuns FROM raspunsuri
                    WHERE id_intrebare = %s
                """, (id_intrebare,))
                answers = cursor.fetchall()
                questions_with_answers.append({
                    'intrebare': intrebare,
                    'raspunsuri': [ans[0] for ans in answers]
                })
            
            quiz_data[numar_chestionar] = questions_with_answers

    except (Exception, psycopg2.Error) as error:
        print("Eroare la vizualizarea chestionarelor:", error)
        flash(f"A intervenit o eroare în timpul vizualizării chestionarelor: {error}", "danger")
        return redirect(url_for('create_contest'))

    finally:
        if connection:
            cursor.close()
            connection.close()

    return render_template('preview_quizzes.html', id_concurs=id_concurs, quizzes=dict(quizzes), quiz_data=quiz_data, username=username)
    





def get_db_connection():
    return psycopg2.connect(
        user="postgres",
        password="vasilica",
        host="192.168.16.164",
        port="5432",
        database="postgres"
    )



@app.route('/edit_contest/<old_id_concurs>', methods=['GET', 'POST'])
def edit_contest(old_id_concurs):
    username = session.get('username')

    if request.method == 'POST':
        new_id_concurs = request.form.get('id_concurs')
        title = request.form.get('title')
        branch = request.form.get('branch') or None  # If empty, set to None
        department = request.form.get('department') or None  # If empty, set to None
        datetime = request.form.get('datetime')
        participants = request.form.getlist('participants')
        id_set = request.form.get('id_set')

        if not all([new_id_concurs, title, datetime, id_set]):
            flash('Toate câmpurile sunt obligatorii!', 'danger')
            return redirect(url_for('edit_contest', old_id_concurs=old_id_concurs))

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("BEGIN")

            # Check if the new `id_concurs` already exists and is not the same as the old one
            cursor.execute("SELECT id_concurs FROM concurs WHERE id_concurs = %s", (new_id_concurs,))
            if cursor.fetchone() and old_id_concurs != new_id_concurs:
                flash(f"ID-ul concursului {new_id_concurs} este deja utilizat. Te rugăm să alegi alt ID.", "danger")
                conn.rollback()
                return redirect(url_for('edit_contest', old_id_concurs=old_id_concurs))

            # Retrieve the current set ID associated with the old contest
            cursor.execute("SELECT id_set FROM concursuri_seturi WHERE id_concurs = %s", (old_id_concurs,))
            current_set_row = cursor.fetchone()
            current_set = current_set_row[0] if current_set_row else None

            if old_id_concurs != new_id_concurs:
                # Insert the new contest
                cursor.execute("""
                    INSERT INTO concurs (id_concurs, titlu, sucursala, departament, data_ora)
                    VALUES (%s, %s, %s, %s, %s)
                """, (new_id_concurs, title, branch, department, datetime))

                # Update foreign key references in all related tables
                cursor.execute("UPDATE concursuri_seturi SET id_concurs = %s WHERE id_concurs = %s", (new_id_concurs, old_id_concurs))
                cursor.execute("UPDATE chestionare SET id_concurs = %s WHERE id_concurs = %s", (new_id_concurs, old_id_concurs))
                cursor.execute("UPDATE participanti_concurs SET id_concurs = %s WHERE id_concurs = %s", (new_id_concurs, old_id_concurs))
                cursor.execute("UPDATE participanti_raspuns SET id_concurs = %s WHERE id_concurs = %s", (new_id_concurs, old_id_concurs))

                # Delete the old contest after updating references
                cursor.execute("DELETE FROM concurs WHERE id_concurs = %s", (old_id_concurs,))
            else:
                # If the ID doesn't change, just update the other details
                cursor.execute("""
                    UPDATE concurs
                    SET titlu = %s, sucursala = %s, departament = %s, data_ora = %s
                    WHERE id_concurs = %s
                """, (title, branch, department, datetime, old_id_concurs))

            # Handle the record in `concursuri_seturi`
            cursor.execute("DELETE FROM concursuri_seturi WHERE id_concurs = %s", (new_id_concurs,))

            if id_set != 'none':
                cursor.execute("""
                    INSERT INTO concursuri_seturi (id_concurs, id_set)
                    VALUES (%s, %s)
                """, (new_id_concurs, id_set))

                # Update quizzes only if the set has changed
                if str(current_set) != str(id_set):  # Comparăm ca stringuri
                    cursor.execute("DELETE FROM chestionar_intrebari WHERE id_chestionar IN (SELECT id_chestionar FROM chestionare WHERE id_concurs = %s)", (new_id_concurs,))
                    cursor.execute("DELETE FROM chestionare WHERE id_concurs = %s", (new_id_concurs,))

                    # Reset is_used for the old set questions if it was used
                    if current_set:
                        cursor.execute("""
                            UPDATE intrebari
                            SET is_used = FALSE
                            WHERE id_set = %s
                        """, (current_set,))

                    cursor.execute("""
                        SELECT id_intrebare FROM intrebari
                        WHERE id_set = %s
                        ORDER BY random()
                    """, (id_set,))
                    questions = cursor.fetchall()

                    if len(questions) < 18:
                        flash("Setul de întrebări nu are suficiente întrebări (minim 18).", "danger")
                        return redirect(url_for('edit_contest', old_id_concurs=old_id_concurs))

                    quiz1_questions = questions[:3]
                    quiz2_questions = questions[3:6]

                    cursor.execute("""
                        INSERT INTO chestionare (id_concurs, numar_chestionar, tip, id_set)
                        VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
                    """, (new_id_concurs, 1, 'standard', id_set, new_id_concurs, 2, 'rezerva', id_set))

                    cursor.execute("""
                        SELECT id_chestionar, tip FROM chestionare
                        WHERE id_concurs = %s
                    """, (new_id_concurs,))
                    quiz_ids = cursor.fetchall()
                    quiz1_id = next(id for id, tip in quiz_ids if tip == 'standard')
                    quiz2_id = next(id for id, tip in quiz_ids if tip == 'rezerva')

                    for question_id in quiz1_questions:
                        cursor.execute("""
                            INSERT INTO chestionar_intrebari (id_chestionar, id_intrebare)
                            VALUES (%s, %s)
                        """, (quiz1_id, question_id[0]))

                    for question_id in quiz2_questions:
                        cursor.execute("""
                            INSERT INTO chestionar_intrebari (id_chestionar, id_intrebare)
                            VALUES (%s, %s)
                        """, (quiz2_id, question_id[0]))

                    # Mark new questions as used
                    cursor.execute("""
                        UPDATE intrebari
                        SET is_used = TRUE
                        WHERE id_set = %s AND id_intrebare IN %s
                    """, (id_set, tuple(q[0] for q in questions)))

            # Handle participants
            cursor.execute("DELETE FROM participanti_concurs WHERE id_concurs = %s", (new_id_concurs,))
            for participant in participants:
                cursor.execute("INSERT INTO participanti_concurs (id_concurs, username) VALUES (%s, %s)", 
                               (new_id_concurs, participant))

            conn.commit()
            flash('Concursul a fost actualizat cu succes!', 'success')
        except Exception as e:
            conn.rollback()
            flash(f"A intervenit o eroare în timpul actualizării concursului: {str(e)}", 'danger')
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('view_contests'))

    else:
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM concurs WHERE id_concurs = %s", (old_id_concurs,))
            contest = cursor.fetchone()
            if not contest:
                flash('Concursul nu a fost găsit!', 'danger')
                return redirect(url_for('view_contests'))

            cursor.execute("SELECT sucursala, departament FROM organizare")
            organizare = cursor.fetchall()

            cursor.execute("SELECT username FROM concurenti ORDER BY username ASC")
            available_participants = [row[0] for row in cursor.fetchall()]

            cursor.execute("SELECT id_set, nume_set FROM seturi_intrebari")
            question_sets = cursor.fetchall()

            cursor.execute("SELECT username FROM participanti_concurs WHERE id_concurs = %s", (old_id_concurs,))
            selected_participants = [row[0] for row in cursor.fetchall()]

            cursor.execute("SELECT id_set FROM concursuri_seturi WHERE id_concurs = %s", (old_id_concurs,))
            selected_set_row = cursor.fetchone()
            selected_set = selected_set_row[0] if selected_set_row else 'none'

            branches_departments = [(item[0], item[1]) for item in organizare]
            branches = list(set([item[0] for item in branches_departments]))

            return render_template('edit_contest.html', contest=contest,
                                   branches=branches,
                                   branches_departments=branches_departments,
                                   available_participants=available_participants,
                                   selected_participants=selected_participants,
                                   question_sets=question_sets,
                                   selected_set=selected_set,
                                   username=username)

        except Exception as e:
            flash(f"A intervenit o eroare în timpul accesării bazei de date: {str(e)}", 'danger')
            return redirect(url_for('view_contests'))
        finally:
            cursor.close()
            conn.close()
























@app.route('/delete_contest/<id_concurs>', methods=['GET'])
@authenticate
def delete_contest(id_concurs):
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()


        cursor.execute("DELETE FROM concursuri_seturi WHERE id_concurs = %s", (id_concurs,))

        cursor.execute("DELETE FROM participanti_concurs WHERE id_concurs = %s", (id_concurs,))


        cursor.execute("DELETE FROM concurs WHERE id_concurs = %s", (id_concurs,))
        
        connection.commit()
        flash("Concursul a fost șters cu succes!", "success")
        return redirect(url_for('view_contests'))
    
    except (Exception, psycopg2.Error) as error:
        print("Eroare la ștergerea concursului:", error)
        flash(f"A intervenit o eroare în timpul ștergerii concursului: {error}", "danger")
        return redirect(url_for('view_contests'))
    
    finally:
        if connection:
            cursor.close()
            connection.close()





@app.route('/view_question_sets', methods=['GET', 'POST'])
@authenticate
def view_question_sets():
    user_type = session['user_type']
    username = session['username']
    question_sets = []
    search_term = request.form.get('search_term') if request.method == 'POST' else request.args.get('search_term')
    column = request.args.get('column', 'id_set') 
    order = request.args.get('order', 'asc')       

    print(f"Search term: {search_term}, Column: {column}, Order: {order}")

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        if search_term:
            query = f"""
                SELECT id_set, nume_set 
                FROM seturi_intrebari 
                WHERE LOWER(nume_set) LIKE LOWER(%s)
                ORDER BY {column} {order.upper()}
            """
            print(f"Executing query with search term: {query}")
            cursor.execute(query, (f'%{search_term}%',))
        else:
            query = f"""
                SELECT id_set, nume_set 
                FROM seturi_intrebari 
                ORDER BY {column} {order.upper()}
            """
            print(f"Executing query without search term: {query}")
            cursor.execute(query)

        question_sets = cursor.fetchall()
        print(f"Fetched question sets: {question_sets}")

    except psycopg2.Error as error:
        print("Eroare la preluarea datelor despre seturile de întrebări:", error)
        flash(f"A intervenit o eroare în timpul preluării datelor despre seturile de întrebări: {error}", "danger")
    finally:
        if connection:
            cursor.close()
            connection.close()

    has_question_sets = bool(question_sets)
    print(f"Has question sets: {has_question_sets}")
    return render_template('view_question_sets.html', question_sets=question_sets, username=username, has_question_sets=has_question_sets, user_type=user_type)





@app.route('/delete_question_set/<id_set>', methods=['GET'])
def delete_question_set(id_set):
    if 'username' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        cursor.execute("DELETE FROM concursuri_seturi WHERE id_set = %s", (id_set,))
        cursor.execute("DELETE FROM chestionare WHERE id_set = %s", (id_set,))

        cursor.execute("DELETE FROM raspunsuri WHERE id_intrebare IN (SELECT id_intrebare FROM intrebari WHERE id_set = %s)", (id_set,))
        cursor.execute("DELETE FROM intrebari WHERE id_set = %s", (id_set,))
        
        cursor.execute("DELETE FROM seturi_intrebari WHERE id_set = %s", (id_set,))

        connection.commit()
        flash('Setul de întrebări a fost șters cu succes!', 'success')
        return redirect(url_for('view_question_sets'))
    except (Exception, Error) as error:
        print("Eroare la ștergerea setului:", error)
        flash(f"A intervenit o eroare în timpul ștergerii setului: {error}", "danger")
        return redirect(url_for('view_question_sets'))
    finally:
        if connection:
            cursor.close()
            connection.close()



 

@app.route('/edit_question_set/<id_set>', methods=['GET', 'POST'])
@authenticate
def edit_question_set(id_set):
    if 'username' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))

    username = session['username']

    if request.method == 'POST':
        new_id_set = request.form.get('id_set')
        nume_set = request.form.get('nume_set')

        if not new_id_set or not nume_set:
            flash(f"Toate câmpurile sunt obligatorii.", "danger")
            return redirect(url_for('edit_question_set', id_set=id_set))

        connection = None
        cursor = None

        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            cursor.execute("BEGIN;")

            # Check if the new set ID already exists
            cursor.execute("SELECT id_set FROM seturi_intrebari WHERE id_set = %s", (new_id_set,))
            id_set_exists = cursor.fetchone()

            if id_set_exists and new_id_set != id_set:
                flash(f"ID-ul nou al setului de întrebări există deja! Te rugăm să alegi un alt ID.", "danger")
                connection.rollback()
                return redirect(url_for('edit_question_set', id_set=id_set))

            if new_id_set != id_set:
                # Insert the new `id_set` in `seturi_intrebari` before updating related tables
                cursor.execute("""
                    INSERT INTO seturi_intrebari (id_set, nume_set)
                    VALUES (%s, %s)
                    ON CONFLICT (id_set) DO NOTHING
                """, (new_id_set, nume_set))

                # Update foreign key references in all related tables
                cursor.execute("UPDATE concursuri_seturi SET id_set = %s WHERE id_set = %s", (new_id_set, id_set))
                cursor.execute("UPDATE intrebari SET id_set = %s WHERE id_set = %s", (new_id_set, id_set))

                # Now, delete the old `id_set` from `seturi_intrebari`
                cursor.execute("DELETE FROM seturi_intrebari WHERE id_set = %s", (id_set,))
            else:
                # If the ID doesn't change, just update the name
                cursor.execute("UPDATE seturi_intrebari SET nume_set = %s WHERE id_set = %s", (nume_set, id_set))

            # Iterate through questions and update or insert them
            for i in range(18):
                question_text = request.form.get(f'questions[{i}][question]')
                question_id = request.form.get(f'questions[{i}][id_intrebare]')
                answer_count = int(request.form.get(f'questions[{i}][answer_count]'))

                if question_text:
                    if question_id:
                        cursor.execute("""
                            UPDATE intrebari 
                            SET intrebare = %s, id_set = %s 
                            WHERE id_intrebare = %s
                        """, (question_text, new_id_set, question_id))
                    else:
                        cursor.execute("""
                            INSERT INTO intrebari (id_set, intrebare) 
                            VALUES (%s, %s) 
                            RETURNING id_intrebare
                        """, (new_id_set, question_text))
                        question_id = cursor.fetchone()[0]

                    # Remove old answers and add new ones
                    cursor.execute("DELETE FROM raspunsuri WHERE id_intrebare = %s", (question_id,))
                    for j in range(answer_count):
                        raspuns = request.form.get(f'questions[{i}][answers][{j}][answer]')
                        punctaj = int(request.form.get(f'questions[{i}][answers][{j}][score]'))

                        if raspuns:
                            cursor.execute("""
                                INSERT INTO raspunsuri (id_intrebare, raspuns, punctaj)
                                VALUES (%s, %s, %s)
                            """, (question_id, raspuns, punctaj))

            connection.commit()
            flash("Setul de întrebări a fost actualizat cu succes!", "success")
            return redirect(url_for('view_question_sets'))

        except (Exception, psycopg2.Error) as error:
            if connection:
                connection.rollback()  # Roll back all changes if there's an error
            flash(f"A intervenit o eroare în timpul actualizării setului de întrebări: {error}", "danger")
            return redirect(url_for('edit_question_set', id_set=id_set))

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    else:
        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            # Fetch existing question set details
            cursor.execute("SELECT id_set, nume_set FROM seturi_intrebari WHERE id_set = %s", (id_set,))
            question_set = cursor.fetchone()

            if not question_set:
                flash(f"Setul de întrebări nu a fost găsit.", "danger")
                return redirect(url_for('view_question_sets'))

            # Fetch associated questions and answers
            cursor.execute("""
                SELECT id_intrebare, intrebare FROM intrebari WHERE id_set = %s ORDER BY id_intrebare ASC
            """, (id_set,))
            questions = cursor.fetchall()

            question_details = []
            for question in questions:
                question_id, question_text = question
                cursor.execute("""
                    SELECT id_raspuns, raspuns, punctaj FROM raspunsuri WHERE id_intrebare = %s ORDER BY id_raspuns ASC
                """, (question_id,))
                answers = cursor.fetchall()
                question_details.append({
                    'id_intrebare': question_id,
                    'intrebare': question_text,
                    'answers': [{'id_raspuns': ans[0], 'raspuns': ans[1], 'punctaj': ans[2]} for ans in answers]
                })

        except (Exception, psycopg2.Error) as error:
            flash(f"A intervenit o eroare în timpul preluării datelor: {error}", "danger")
            return redirect(url_for('view_question_sets'))

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    return render_template('edit_question_set.html', question_set=question_set, question_details=question_details, username=username, enumerate=enumerate)

  





@app.route('/create_branch', methods=['GET', 'POST'])
def create_branch():
    username = session.get('username')

    if request.method == 'POST':
        branch = request.form['branch']

        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            cursor.execute("SELECT * FROM sucursale WHERE sucursala = %s", (branch,))
            existing_branch = cursor.fetchone()

            if existing_branch:
                flash(f"Această sucursală există deja!", "danger")
                return redirect(url_for('create_branch'))

            cursor.execute("INSERT INTO sucursale (sucursala) VALUES (%s)", (branch,))
            connection.commit()
            flash(f"Sucursala {branch} a fost adăugată cu succes!", "success")
            return redirect(url_for('view_branches'))

        except (Exception, psycopg2.Error) as error:
            print("Eroare la crearea sucursalei:", error)
            flash(f"A intervenit o eroare în timpul creării sucursalei: {error}", "danger")
            return redirect(url_for('create_branch'))

        finally:
            if connection:
                cursor.close()
                connection.close()

    return render_template('create_branch.html', username=username)



@app.route('/create_department', methods=['GET', 'POST'])
@authenticate
def create_department():
    username =  session.get('username')

    if request.method == 'POST':
        branch = request.form['branch']
        departments = request.form.getlist('department[]')

        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            for department in departments:
                cursor.execute("SELECT * FROM organizare WHERE sucursala = %s AND departament = %s", (branch, department))
                existing_department = cursor.fetchone()

                if existing_department:
                    flash(f"Departamentul {department} există deja în sucursala {branch}!", "danger")
                    return redirect(url_for('create_department'))

                cursor.execute("INSERT INTO organizare (sucursala, departament) VALUES (%s, %s)", (branch, department))

            connection.commit()
            flash(f"Departamentele au fost adăugate cu succes!", "success")
            return redirect(url_for('view_department'))

        except (Exception, psycopg2.Error) as error:
            print("Eroare la crearea departamentului:", error)
            flash(f"A intervenit o eroare în timpul creării departamentului: {error}", "danger")
            return redirect(url_for('create_department'))

        finally:
            if connection:
                cursor.close()
                connection.close()

    else:
        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()
            cursor.execute("SELECT sucursala FROM sucursale ORDER BY sucursala ASC")
            sucursale = cursor.fetchall()

        except (Exception, psycopg2.Error) as error:
            print("Eroare la preluarea sucursalelor:", error)
            flash(f"A intervenit o eroare în timpul preluării sucursalelor: {error}", "danger")
            sucursale = []

        finally:
            if connection:
                cursor.close()
                connection.close()

    return render_template('create_department.html', username=username, sucursale=sucursale)



@app.route('/edit_department/<sucursala>/<departament>', methods=['GET', 'POST'])
@authenticate
def edit_department(sucursala, departament):
    username = session['username']

    if request.method == 'POST':
        new_department = request.form['department']
        new_sucursala = request.form['sucursala']

        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            # Actualizare departament în tabela organizare
            cursor.execute("""
                UPDATE organizare
                SET sucursala = %s, departament = %s
                WHERE sucursala = %s AND departament = %s
            """, (new_sucursala, new_department, sucursala, departament))

            # Actualizare departament în tabela concurs
            cursor.execute("""
                UPDATE concurs
                SET sucursala = %s, departament = %s
                WHERE sucursala = %s AND departament = %s
            """, (new_sucursala, new_department, sucursala, departament))

            connection.commit()
            flash(f"Departamentul a fost actualizat cu succes!", "success")

        except psycopg2.Error as error:
            print("Eroare PostgreSQL:", error)
            flash(f"A intervenit o eroare în timpul actualizării departamentului: {error}", "danger")
        finally:
            if connection:
                cursor.close()
                connection.close()

        return redirect(url_for('view_department'))

    else:
        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            cursor.execute("SELECT sucursala FROM sucursale ORDER BY sucursala ASC")
            rows = cursor.fetchall()
            branches = [row[0] for row in rows]

        except psycopg2.Error as error:
            print("Eroare PostgreSQL:", error)
            flash(f"A intervenit o eroare în timpul preluării sucursalelor: {error}", "danger")
        finally:
            if connection:
                cursor.close()
                connection.close()

        return render_template('edit_department.html', username=username, sucursala=sucursala, departament=departament, branches=branches)



@app.route('/view_department', methods=['GET'])
@authenticate
def view_department():
    username = session['username']
    user_type = session['user_type']
    branches = []
    search_query = request.args.get('query', '').lower()
    column = request.args.get('column', 'sucursala')
    order = request.args.get('order', 'asc')

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        if search_query:
            cursor.execute(f"""
                SELECT sucursala, departament
                FROM organizare
                WHERE LOWER(sucursala) LIKE %s
                OR LOWER(departament) LIKE %s
                ORDER BY {column} {order.upper()}
            """, (f'%{search_query}%', f'%{search_query}%'))
        else:
            cursor.execute(f"SELECT sucursala, departament FROM organizare ORDER BY {column} {order.upper()}")

        rows = cursor.fetchall()
        for row in rows:
            branches.append({
                'sucursala': row[0],
                'departament': row[1]
            })

    except psycopg2.Error as error:
        print("Eroare PostgreSQL:", error)
        flash(f"A intervenit o eroare în timpul preluării datelor despre sucursale și departamente: {error}", "danger")
    finally:
        if connection:
            cursor.close()
            connection.close()
    has_branches = bool(branches)  
    return render_template('view_department.html', branches=branches, username=username, has_branches=has_branches, column=column, order=order, user_type=user_type)


@app.route('/delete_department/<sucursala>/<departament>', methods=['GET', 'POST'])
@authenticate
def delete_department(sucursala, departament):
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()
        cursor.execute("""
            DELETE FROM organizare
            WHERE sucursala = %s AND departament = %s
        """, (sucursala, departament))
        
        connection.commit()
        flash(f"Departamentul {departament} a fost șters cu succes.", "success")

    except psycopg2.Error as error:
        print("Eroare PostgreSQL:", error)
        flash(f"A intervenit o eroare în timpul ștergerii departamentului: {error}", "danger")
    finally:
        if connection:
            cursor.close()
            connection.close()

    return redirect(url_for('view_department'))


@app.route('/view_branches', methods=['GET'])
@authenticate
def view_branches():
    username = session['username']
    user_type = session['user_type']
    branches = []
    search_query = request.args.get('query', '').lower()
    column = request.args.get('column', 'sucursala')
    order = request.args.get('order', 'asc')

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        if search_query:
            cursor.execute(f"""
                SELECT sucursala
                FROM sucursale
                WHERE LOWER(sucursala) LIKE %s
                ORDER BY {column} {order.upper()}
            """, (f'%{search_query}%',))
        else:
            cursor.execute(f"SELECT sucursala FROM sucursale ORDER BY {column} {order.upper()}")

        rows = cursor.fetchall()
        for row in rows:
            branches.append({
                'sucursala': row[0]
            })

    except psycopg2.Error as error:
        print("Eroare PostgreSQL:", error)
        flash(f"A intervenit o eroare în timpul preluării sucursalelor: {error}", "danger")
    finally:
        if connection:
            cursor.close()
            connection.close()
    has_branches = bool(branches)  
    return render_template('view_branches.html', branches=branches, username=username, has_branches=has_branches, column=column, order=order, user_type=user_type)



@app.route('/edit_branch/<sucursala>', methods=['GET', 'POST'])
@authenticate
def edit_branch(sucursala):
    username = session['username']
    
    if request.method == 'POST':
        new_sucursala = request.form['sucursala']

        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()
            cursor.execute("""
                UPDATE sucursale
                SET sucursala = %s
                WHERE sucursala = %s
            """, (new_sucursala, sucursala))

            cursor.execute("""
                UPDATE concurs
                SET sucursala = %s
                WHERE sucursala = %s
            """, (new_sucursala, sucursala))

            cursor.execute("""
                UPDATE organizare
                SET sucursala = %s
                WHERE sucursala = %s
            """, (new_sucursala, sucursala))

            connection.commit()
            flash(f"Sucursala {sucursala} a fost actualizată cu succes!", "success")

        except psycopg2.Error as error:
            print("Eroare PostgreSQL:", error)
            flash(f"A intervenit o eroare în timpul actualizării sucursalei: {error}", "danger")
        finally:
            if connection:
                cursor.close()
                connection.close()

        return redirect(url_for('view_branches'))

    else:
        return render_template('edit_branch.html', username=username, sucursala=sucursala)



@app.route('/delete_branch/<sucursala>', methods=['POST'])
@authenticate
def delete_branch(sucursala):
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        # Set sucursala to NULL or 'None' in related tables before deletion
        cursor.execute("""
            UPDATE concurs
            SET sucursala = NULL  -- or 'None'
            WHERE sucursala = %s
        """, (sucursala,))

        cursor.execute("""
            UPDATE organizare
            SET sucursala = NULL  -- or 'None'
            WHERE sucursala = %s
        """, (sucursala,))

        # Delete the branch from sucursale table
        cursor.execute("""
            DELETE FROM sucursale
            WHERE sucursala = %s
        """, (sucursala,))

        connection.commit()
        flash(f"Sucursala {sucursala} a fost ștearsă cu succes!", "success")

    except psycopg2.Error as error:
        print("Eroare PostgreSQL:", error)
        flash(f"A intervenit o eroare în timpul ștergerii sucursalei: {error}", "danger")
    finally:
        if connection:
            cursor.close()
            connection.close()

    return redirect(url_for('view_branches'))





@app.route('/view_test/<int:id_set>', methods=['GET', 'POST'])
def view_test(id_set):
    username = session['username']
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        id_concurs = request.args.get('id_concurs')

        if not id_concurs or not id_concurs.isdigit():
            flash(f"Id-ul concursului lipsește sau nu este valid.", "danger")
            return redirect(url_for('view_question_sets'))

        username = session['username']
        cursor.execute("SELECT 1 FROM participanti_concurs WHERE username = %s AND id_concurs = %s", (username, id_concurs))
        user_is_participant = cursor.fetchone()

        if not user_is_participant:
            flash(f"Utilizatorul nu este participant la acest concurs.", "danger")
            return redirect(url_for('view_question_sets'))

        if request.method == 'POST':
            print("Form data received:")
            print(request.form)
            answers = request.form.to_dict(flat=False)
            print("Answers dict:")
            print(answers)
            for q_id, answer_ids in answers.items():
                if answer_ids and q_id.startswith('question_'):
                    q_id = q_id.split('_')[1]  # Extract the actual question ID
                    for answer_id in answer_ids:
                        try:
                            numeric_answer_id = int(''.join(filter(str.isdigit, str(answer_id))))
                            print(f"Inserting answer for question {q_id}, answer_id {numeric_answer_id}")
                            cursor.execute("""
                                INSERT INTO participanti_raspuns (username, id_concurs, id_intrebare, id_raspuns)
                                VALUES (%s, %s, %s, %s)
                            """, (username, id_concurs, q_id, numeric_answer_id))
                        except ValueError:
                            print(f"Invalid answer ID: {answer_id} for question {q_id}")
                            continue  # Skip this answer and continue with the next

            connection.commit()
            flash(f"Testul a fost trimis cu succes!", "success")
            return redirect(url_for('view_question_sets'))


        cursor.execute("""
            SELECT i.id_intrebare, i.intrebare, r.id_raspuns, r.raspuns, r.punctaj
            FROM intrebari i
            LEFT JOIN raspunsuri r ON i.id_intrebare = r.id_intrebare
            WHERE i.id_set = %s
            ORDER BY i.id_intrebare
        """, (id_set,))
        rows = cursor.fetchall()
        questions = {}

        for row in rows:
            question_id, question_text, answer_id, answer_text, score = row
            if question_id not in questions:
                questions[question_id] = {
                    'question_text': question_text,
                    'answers': []
                }
            if answer_id:
                questions[question_id]['answers'].append({
                    'answer_id': answer_id,
                    'answer_text': answer_text,
                    'score': score
                })

        return render_template('view_test.html', questions=questions, id_set=id_set, id_concurs=id_concurs,  username=username)

    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea întrebărilor:", error)
        flash(f"A intervenit o eroare în timpul preluării întrebărilor: {error}", "danger")
        return redirect(url_for('view_question_sets'))

    finally:
        if connection:
            cursor.close()
            connection.close()




@app.route('/solve_quiz/<int:id_chestionar>', methods=['GET', 'POST'])
def solve_quiz(id_chestionar):
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    if request.method == 'POST':
        answers = request.form
        id_concurs = request.form.get('id_concurs')  

        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            total_score = 10  

            for question_key, answer_ids in answers.items():
                if question_key.startswith('question_'):
                    question_id = int(question_key.split('_')[1].strip('[]'))

                    if isinstance(answer_ids, str):
                        answer_ids = [answer_ids]  

                    valid_answer_ids = []
                    for raw_answer_id in answer_ids:
                        try:
                            clean_answer_id = raw_answer_id.strip('[]').strip()
                            answer_id_int = int(clean_answer_id)
                            valid_answer_ids.append(answer_id_int)
                        except ValueError:
                            print(f"Invalid answer ID: {raw_answer_id}")
                            continue

                    if not valid_answer_ids:
                        continue

                    cursor.execute("""
                        SELECT id_raspuns, punctaj FROM raspunsuri WHERE id_intrebare = %s
                    """, (question_id,))
                    correct_answers = cursor.fetchall()
                    correct_answer_ids = {answer[0] for answer in correct_answers}
                    correct_answer_points = {answer[0]: answer[1] for answer in correct_answers}

                    if all(answer_id in correct_answer_ids for answer_id in valid_answer_ids):
                       
                        score = sum(correct_answer_points[answer_id] for answer_id in valid_answer_ids)
                    else:
                  
                        score = 0

                    total_score += score  

                    for answer_id in valid_answer_ids:
                        cursor.execute("""
                            INSERT INTO participanti_raspuns (username, id_concurs, id_intrebare, id_raspuns, punctaj)
                            VALUES (%s, %s::VARCHAR, %s, %s, %s)
                        """, (username, id_concurs, question_id, answer_id, score))

            cursor.execute("""
                SELECT 1 FROM participanti_scoruri WHERE username = %s AND id_concurs = %s AND id_set = %s
            """, (username, id_concurs, id_chestionar))
            existing_score = cursor.fetchone()

            if existing_score:
                cursor.execute("""
                    UPDATE participanti_scoruri
                    SET scor_total = %s
                    WHERE username = %s AND id_concurs = %s AND id_set = %s
                """, (total_score, username, id_concurs, id_chestionar))
            else:
                cursor.execute("""
                    INSERT INTO participanti_scoruri (username, id_concurs, id_set, scor_total)
                    VALUES (%s, %s::VARCHAR, %s, %s)
                """, (username, id_concurs, id_chestionar, total_score))

            cursor.execute("""
                INSERT INTO participanti_concurs (id_concurs, username, scor_total)
                VALUES (%s::VARCHAR, %s, %s)
                ON CONFLICT (id_concurs, username) 
                DO UPDATE SET scor_total = GREATEST(participanti_concurs.scor_total, %s)
            """, (id_concurs, username, total_score, total_score))

            connection.commit()

            return redirect(url_for('test_report', id_concurs=id_concurs, id_set=id_chestionar, username=username, total_score=total_score))

        except (Exception, psycopg2.Error) as error:
            print("Eroare la salvarea răspunsurilor:", error)
            flash(f"A intervenit o eroare: {error}", "danger")
            return redirect(url_for('view_contest', id_concurs=id_concurs))  
        finally:
            if connection:
                cursor.close()
                connection.close()

    else:
        questions = {}

        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            cursor.execute("""
                SELECT id_concurs FROM chestionare WHERE id_chestionar = %s
            """, (id_chestionar,))
            result = cursor.fetchone()
            if result is None:
                flash("Nu am găsit concursul asociat cu acest chestionar.", "danger")
                return redirect(url_for('view_contests'))

            id_concurs = result[0]

            cursor.execute("""
                SELECT i.id_intrebare, i.intrebare, r.id_raspuns, r.raspuns
                FROM intrebari i
                JOIN raspunsuri r ON i.id_intrebare = r.id_intrebare
                WHERE i.id_intrebare IN (
                    SELECT id_intrebare FROM chestionar_intrebari WHERE id_chestionar = %s
                )
                ORDER BY i.id_intrebare, r.id_raspuns
            """, (id_chestionar,))
            rows = cursor.fetchall()

            for row in rows:
                question_id, question_text, answer_id, answer_text = row
                if question_id not in questions:
                    questions[question_id] = {
                        'question_text': question_text,
                        'answers': []
                    }
                questions[question_id]['answers'].append({
                    'answer_id': answer_id,
                    'answer_text': answer_text
                })

            question_list = list(questions.items())
            random.shuffle(question_list)
            questions = dict(question_list)

            for question in questions.values():
                random.shuffle(question['answers'])

        except (Exception, psycopg2.Error) as error:
            print("Eroare la obținerea întrebărilor și răspunsurilor:", error)
            flash(f"A intervenit o eroare: {error}", "danger")
            return redirect(url_for('view_contest', id_concurs=id_concurs))

        finally:
            if connection:
                cursor.close()
                connection.close()

        return render_template('solve_quiz.html', questions=questions, id_concurs=id_concurs, id_chestionar=id_chestionar)



@app.route('/contest/<int:id_concurs>', methods=['GET'])
def view_contest(id_concurs):
    if 'username' not in session:
        return redirect(url_for('login'))

    quizzes = []
    standard_completed = False
    reserve_completed = False

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        cursor.execute("""
            SELECT id_chestionar, tip
            FROM chestionare
            WHERE id_concurs = %s::VARCHAR
            ORDER BY CASE WHEN tip = 'standard' THEN 1 ELSE 2 END;
        """, (str(id_concurs),))
        quizzes = cursor.fetchall()

        
        cursor.execute("""
            SELECT COUNT(pr.id_raspuns)
            FROM participanti_raspuns pr
            JOIN chestionar_intrebari ci ON pr.id_intrebare = ci.id_intrebare
            JOIN chestionare c ON ci.id_chestionar = c.id_chestionar
            WHERE pr.username = %s AND c.id_concurs = %s AND c.tip = 'standard';
        """, (session['username'], str(id_concurs)))
        standard_completed = cursor.fetchone()[0] > 0

        
        cursor.execute("""
            SELECT COUNT(pr.id_raspuns)
            FROM participanti_raspuns pr
            JOIN chestionar_intrebari ci ON pr.id_intrebare = ci.id_intrebare
            JOIN chestionare c ON ci.id_chestionar = c.id_chestionar
            WHERE pr.username = %s AND c.id_concurs = %s AND c.tip = 'rezerva';
        """, (session['username'], str(id_concurs)))
        reserve_completed = cursor.fetchone()[0] > 0

    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea datelor:", error)
        flash(f"A intervenit o eroare: {error}", "danger")
    finally:
        if connection:
            cursor.close()
            connection.close()

    return render_template('contest.html', id_concurs=id_concurs, standard_completed=standard_completed, reserve_completed=reserve_completed, quizzes=quizzes)


@app.route('/test_report/<int:id_concurs>/<int:id_set>/<username>/<int:total_score>', methods=['GET', 'POST'])
def test_report(id_concurs, id_set, username, total_score):
    if 'username' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            # Obține conținutul PDF-ului din request
            pdf_content = request.files['pdf_file'].read()

            # Setup database connection
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            # Salvează conținutul PDF în baza de date
            cursor.execute("""
                UPDATE participanti_scoruri
                SET raport_pdf = %s
                WHERE id_concurs = %s::VARCHAR AND username = %s
            """, (psycopg2.Binary(pdf_content), str(id_concurs), username))

            connection.commit()

            return jsonify({'status': 'PDF saved successfully'})

        except (Exception, psycopg2.Error) as error:
            print("Eroare la salvarea raportului PDF:", error)
            flash(f"A intervenit o eroare în timpul salvării raportului PDF: {error}", "danger")
            return redirect(url_for('view_contest', id_concurs=str(id_concurs)))

        finally:
            if connection:
                cursor.close()
                connection.close()

    else:
        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            # Obține întrebările și răspunsurile
            cursor.execute("""
                SELECT i.id_intrebare, i.intrebare, r.id_raspuns, r.raspuns, r.punctaj,
                    pr.id_raspuns AS user_answer_id
                FROM intrebari i
                LEFT JOIN raspunsuri r ON i.id_intrebare = r.id_intrebare
                LEFT JOIN participanti_raspuns pr ON i.id_intrebare = pr.id_intrebare
                    AND r.id_raspuns = pr.id_raspuns
                    AND pr.username = %s
                    AND pr.id_concurs = %s::VARCHAR
                WHERE i.id_intrebare IN (
                    SELECT id_intrebare FROM chestionar_intrebari WHERE id_chestionar = %s
                )
                ORDER BY i.id_intrebare, r.id_raspuns
            """, (username, str(id_concurs), id_set))

            rows = cursor.fetchall()
            questions = {}

            for row in rows:
                question_id, question_text, answer_id, answer_text, score, user_answer_id = row
                if question_id not in questions:
                    questions[question_id] = {
                        'question_text': question_text,
                        'answers': [],
                        'user_answered_correctly': True,  # Default to True until proven otherwise
                        'total_score': 0  # Default score for the question
                    }

                is_correct = user_answer_id is not None and score > 0
                selected = user_answer_id == answer_id

                if selected and not is_correct:
                    questions[question_id]['user_answered_correctly'] = False

                if selected:
                    questions[question_id]['total_score'] += score  # Add the score for the selected answer

                questions[question_id]['answers'].append({
                    'answer_id': answer_id,
                    'answer_text': answer_text,
                    'score': score,
                    'is_correct': is_correct,
                    'selected': selected
                })

            return render_template('test_report.html', questions=questions, total_score=total_score, username=username, id_concurs=id_concurs)

        except (Exception, psycopg2.Error) as error:
            print("Eroare la preluarea raportului testului:", error)
            flash(f"A intervenit o eroare în timpul preluării raportului testului: {error}", "danger")
            return redirect(url_for('view_contest', id_concurs=str(id_concurs)))

        finally:
            if connection:
                cursor.close()
                connection.close()






@app.route('/view_users', methods=['GET', 'POST'])
@authenticate
def view_users():
    username = session['username']
    user_type = session['user_type']
    users = []
    search_query = request.args.get('query', '').lower()
    column = request.args.get('column', 'username')
    order = request.args.get('order', 'asc')

    column_mapping = {
        'id': 'u.id',
        'username': 'u.username',
        'user_type': 'u.user_type'
    }

    if column not in column_mapping:
        column = 'username'

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        query = """
            SELECT u.id, u.username, u.user_type
            FROM users u
        """

        if search_query:
            query += """
                WHERE LOWER(u.username) LIKE %s
                OR CAST(u.id AS TEXT) LIKE %s
                OR LOWER(u.user_type) LIKE %s
            """
            search_param = f"%{search_query}%"
            cursor.execute(query, (search_param, search_param, search_param))
        else:
            cursor.execute(query)

        users = cursor.fetchall()

    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea datelor din PostgreSQL:", error)
    finally:
        if connection:
            cursor.close()
            connection.close()

    users_data = []
    for user in users:
        users_data.append({
            'id': user[0],
            'username': user[1],
            'user_type': user[2]
        })

    # Sorting logic
    reverse_order = (order == 'desc')
    users_data.sort(key=lambda x: str(x[column]), reverse=reverse_order)

    has_users = len(users_data) > 0

    return render_template(
        'view_users.html',
        username=username,
        user_type=user_type,
        users=users_data,
        has_users=has_users,
        column=column,
        order=order
    )



@app.route('/edit_user/<int:id>', methods=['GET', 'POST'])
@authenticate
def edit_user(id):
    username = session.get('username')  
    if request.method == 'POST':
        new_username = request.form.get('username')
        password = request.form.get('password')
        user_type = request.form.get('user_type')

        if not new_username:
            flash("Username-ul este obligatoriu!", "danger")
            return redirect(url_for('edit_user', id=id))

        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            cursor.execute("SELECT username FROM users WHERE username = %s AND id != %s", (new_username, id))
            if cursor.fetchone():
                flash("Username-ul există deja! Te rog să alegi altul.", "danger")
                return redirect(url_for('edit_user', id=id))

            if password:
                hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                cursor.execute("""
                    UPDATE users
                    SET username = %s, password = %s, user_type = %s
                    WHERE id = %s
                """, (new_username, hashed_password.decode('utf-8'), user_type, id))
            else:
                cursor.execute("""
                    UPDATE users
                    SET username = %s, user_type = %s
                    WHERE id = %s
                """, (new_username, user_type, id))

            connection.commit()
            flash("Utilizatorul a fost actualizat cu succes!", "success")
            return redirect(url_for('view_users'))

        except (Exception, psycopg2.Error) as error:
            print("Eroare la actualizare:", error)
            connection.rollback()  
            flash(f"A apărut o eroare la actualizare: {error}", "danger")
            return redirect(url_for('edit_user', id=id))
        finally:
            if connection:
                cursor.close()
                connection.close()
    else:
        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="192.168.16.164",
                port="5432",
                database="postgres"
            )
            cursor = connection.cursor()

            cursor.execute("SELECT id, username, user_type FROM users WHERE id = %s", (id,))
            user = cursor.fetchone()

            if user:
                return render_template('edit_user.html', user=user, username=username) 
            else:
                flash("Utilizatorul nu a fost găsit.", "danger")
                return redirect(url_for('view_users'))

        except (Exception, psycopg2.Error) as error:
            print("Eroare de bază de date:", error)
            flash(f"Eroare de bază de date: {error}", "danger")
            return redirect(url_for('view_users'))
        finally:
            if connection:
                cursor.close()
                connection.close()


@app.route('/delete_user/<int:id>')
def delete_user(id):
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="192.168.16.164",
            port="5432",
            database="postgres"
        )
        cursor = connection.cursor()

        connection.autocommit = False 

        cursor.execute("SELECT username FROM users WHERE id = %s", (id,))
        username = cursor.fetchone()

        if username:
            username = username[0]

            cursor.execute("DELETE FROM participanti_concurs WHERE username = %s", (username,))
            cursor.execute("DELETE FROM participanti_raspuns WHERE username = %s", (username,))
            cursor.execute("DELETE FROM participanti_scoruri WHERE username = %s", (username,))
 
            cursor.execute("DELETE FROM users WHERE id = %s", (id,))

            connection.commit()

            flash("Utilizatorul a fost șters cu succes!", "success")
        else:
            flash("Utilizatorul nu a fost găsit.", "danger")

    except (Exception, psycopg2.Error) as error:
        print("Eroare la ștergere:", error)
        connection.rollback()  
        flash(f"A apărut o eroare în timpul ștergerii: {error}", "danger")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for('view_users'))



if __name__ == '__main__':
     app.run(host="0.0.0.0", port=5000, debug=True)

 
