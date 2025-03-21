from flask import (
    Flask,
    render_template,
    request,
    make_response,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    g,
)
from flask_cors import CORS
import psycopg2
from psycopg2 import Error
from functools import wraps
import bcrypt
import random
import re
from datetime import datetime, timedelta

app = Flask(__name__)
CORS(app)
app.secret_key = "your_secret_key"
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0


@app.after_request
def apply_csp(response):
    response.headers["Content-Security-Policy"] = (
        "connect-src 'self' http://localhost:5055"
    )
    # Re-request page when pressing back in the browser
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = "0"

    return response


def connect_db():
    return psycopg2.connect(
        user="postgres",
        password="vasilica",
        host="0",
        port="5432",
        database="postgres",
    )


# ----------------------------------------DECORATORS----------------------------------------


# Authentication decorator
def authenticate(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login"))

        user = get_user(session["username"])
        competitor = get_competitor(session["username"])

        if not user and not competitor:
            return (
                jsonify(
                    {
                        "message": "Utilizatorul nu are permisiunea necesară pentru acces."
                    }
                ),
                403,
            )

        return f(*args, **kwargs)

    return decorated


# Role-based access control decorator
def authorize(roles):
    def wrapper(f): 
        @wraps(f)
        def decorated(*args, **kwargs): 
            if session["user_type"] not in roles:  
                return (
                    jsonify({"message": "Permisiune refuzata!"}),
                    403,
                )  
            return f(*args, **kwargs)  

        return decorated  

    return wrapper  

# ----------------------------------------FUNCTIONS----------------------------------------


# Check credentials function (verify in database)
def check_credentials(username, password):
    try:
        connection = connect_db()
        cursor = connection.cursor()

        # Check if the user exists in 'users' table
        cursor.execute(
            "SELECT username, password, user_type FROM users WHERE username = %s",
            (username,),
        )
        user = cursor.fetchone()

        if not user:
            # If user does not exist in 'users' table, check 'concurenti' table
            cursor.execute(
                "SELECT username, password,  user_type FROM concurenti WHERE username = %s",
                (username,),
            )
            concurent = cursor.fetchone()
            if concurent:
                user = (concurent[0], concurent[1], "concurent")

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
        connection = connect_db()
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
            host="0",
            port="5432",
            database="postgres",
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


# ----------------------------------------ROUTES----------------------------------------
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user = check_credentials(username, password)

        if user:
            stored_password = user[1]
            if bcrypt.checkpw(
                password.encode("utf-8"), stored_password.encode("utf-8")
            ):
                session["username"] = user[0]
                session["user_type"] = user[2]
                g.current_user = {"username": user[0], "user_type": user[2]}
                print("Sesiune dupa login:", session)

                response = make_response(jsonify({"message": "ok"}))
                return response
        flash("Utilizatorul sau parola au fost introduse greșit.", "danger")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr'])
def register():
    username = session["username"]
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        user_type = request.form["user_type"]
        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="0",
                port="5432",
                database="postgres",
            )
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO users (username, password, user_type) VALUES (%s, %s, %s)",
                (username, hashed_password.decode("utf-8"), user_type),
            )
            connection.commit()
            flash("Utilizator înregistrat cu succes!", "success")
            return redirect(url_for("view_users"))
        except (Exception, Error) as error:
            print("Eroare la înregistrare:", error)
            flash(f"A apărut o eroare la înregistrare: {error}", "danger")
            return redirect(url_for("register"))
        finally:
            if connection:
                cursor.close()
                connection.close()
    return render_template("register.html", username=username)


@app.route("/register_contestant", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def register_contestant():
    username = session["username"]
    contests = []

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="0",
            port="5432",
            database="postgres",
        )
        cursor = connection.cursor()

        cursor.execute("SELECT id_concurs, titlu FROM concurs")
        contests = cursor.fetchall()

        if request.method == "POST":
            username = request.form["username"]
            password = request.form["password"]
            user_type = request.form["user_type"]
            nume_prenume = request.form["nume_prenume"]
            selected_contests = set(map(int, request.form.getlist("contests")))

            hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

            cursor.execute(
                "INSERT INTO concurenti (username, password, user_type, nume_prenume) VALUES (%s, %s, %s, %s)",
                (username, hashed_password.decode("utf-8"), user_type, nume_prenume),
            )

            for contest_id in selected_contests:
                cursor.execute(
                    """
                    INSERT INTO participanti_concurs (id_concurs, username)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (contest_id, username),
                )

            connection.commit()
            flash("Concurent înregistrat cu succes!", "success")
            return redirect(url_for("view_contestants"))

    except (Exception, Error) as error:
        if connection:
            connection.rollback()
        print("Eroare la înregistrare:", error)
        flash(f"A apărut o eroare la înregistrare: {error}", "danger")
        return redirect(url_for("register_contestant"))
    finally:
        if connection:
            cursor.close()
            connection.close()

    return render_template("register_contestant.html", username=username, contests=contests)


@app.route("/view_contestants", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def view_contestants():
    username = session["username"]
    user_type = session["user_type"]
    contestants = []
    search_query = request.args.get("query", "").lower()
    column = request.args.get("column", "username")
    order = request.args.get("order", "asc")

    # ➕ Adăugat în column_mapping
    column_mapping = {
        "id": "c.id",
        "username": "c.username",
        "user_type": "c.user_type",
        "nume_prenume": "c.nume_prenume",
        "contests_assigned": "contests_assigned",
    }

    if column not in column_mapping:
        column = "username"

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="c",
            port="5432",
            database="postgres",
        )
        cursor = connection.cursor()

        # ➕ Adăugat câmpul c.nume_prenume în SELECT
        query = """
            SELECT c.id, c.username, c.user_type, c.nume_prenume,
                   array_agg(pc.id_concurs) AS assigned_contests,
                   array_agg(concurs.titlu) AS contest_titles
            FROM concurenti c
            LEFT JOIN participanti_concurs pc ON c.username = pc.username
            LEFT JOIN concurs ON pc.id_concurs = concurs.id_concurs
        """

        if search_query:
            query += """
                WHERE LOWER(c.username) LIKE %s 
                OR LOWER(concurs.titlu) LIKE %s
                OR LOWER(c.nume_prenume) LIKE %s
                OR CAST(c.id AS TEXT) LIKE %s
            """
            search_param = f"%{search_query}%"
            cursor.execute(
                query + " GROUP BY c.id, c.username, c.user_type, c.nume_prenume",
                (search_param, search_param, search_param, search_param),
            )
        else:
            cursor.execute(query + " GROUP BY c.id, c.username, c.user_type, c.nume_prenume")

        contestants = cursor.fetchall()

        contestants_data = []
        for contestant in contestants:
            contests_assigned = []
            if contestant[4] != [None] and contestant[5] != [None]:
                for i in range(len(contestant[4])):
                    cursor.execute(
                        "SELECT id_set, scor_total FROM participanti_scoruri WHERE id_concurs = %s AND username = %s",
                        (contestant[4][i], contestant[1]),
                    )
                    rows = cursor.fetchall()
                    variants = []
                    for row in rows:
                        variants.append(
                            {
                                "id_set": row[0],
                                "total_score": row[1],
                                "title": "Standard" if len(variants) == 0 else "Rezerva",
                                "completed": row[1] is not None,
                            }
                        )

                    contests_assigned.append(
                        {
                            "id": contestant[4][i],
                            "titlu": contestant[5][i],
                            "variants": variants,
                        }
                    )

            contestants_data.append(
                {
                    "id": contestant[0],
                    "username": contestant[1],
                    "user_type": contestant[2],
                    "nume_prenume": contestant[3],  # ➕ Adăugat aici
                    "contests_assigned": contests_assigned,
                }
            )

    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea datelor din PostgreSQL:", error)
    finally:
        if connection:
            cursor.close()
            connection.close()

    # Sorting logic
    reverse_order = order == "desc"
    if column == "contests_assigned":
        contestants_data.sort(key=lambda x: len(x["contests_assigned"]), reverse=reverse_order)
    else:
        contestants_data.sort(key=lambda x: x[column], reverse=reverse_order)

    has_contestants = len(contestants_data) > 0

    return render_template(
        "view_contestants.html",
        username=username,
        user_type=user_type,
        contestants=contestants_data,
        has_contestants=has_contestants,
        column=column,
        order=order,
    )



@app.route("/edit_contestant/<int:id>", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def edit_contestant(id):
    conn = None
    cursor = None
    username = session["username"]

    try:
        conn = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="0",
            port="5432",
            database="postgres",
        )
        cursor = conn.cursor()

        if request.method == "POST":
            old_username = request.form.get("old_username")
            new_username = request.form.get("username")
            password = request.form.get("password")
            
            nume_prenume = request.form.get("nume_prenume")

            selected_contests = set(map(int, request.form.getlist("contests")))

            if not new_username or not nume_prenume:
                flash("Username-ul și numele complet sunt obligatorii!", "danger")
                return redirect(url_for("edit_contestant", id=id))

            cursor.execute("BEGIN;")

            if password:
                hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
            else:
                cursor.execute("SELECT password FROM concurenti WHERE username = %s", (old_username,))
                hashed_password = cursor.fetchone()[0]

            if new_username != old_username:
                cursor.execute("""
                    UPDATE concurenti
                    SET username = %s, password = %s, nume_prenume = %s
                    WHERE username = %s
                """, (new_username, hashed_password, nume_prenume, old_username))
            else:
                cursor.execute("""
                    UPDATE concurenti
                    SET password = %s, nume_prenume = %s
                    WHERE id = %s
                """, (hashed_password, nume_prenume, id))  # ➕ aici am adăugat și nume_prenume

            cursor.execute("SELECT id_concurs FROM participanti_concurs WHERE username = %s", (new_username,))
            current_contests = set(row[0] for row in cursor.fetchall())

            cursor.execute("SELECT DISTINCT id_concurs FROM participanti_scoruri WHERE username = %s", (new_username,))
            completed_contests = set(row[0] for row in cursor.fetchall())

            contests_to_remove = current_contests - selected_contests - completed_contests
            contests_to_add = selected_contests - current_contests - completed_contests

            if contests_to_remove:
                cursor.execute("""
                    DELETE FROM participanti_concurs
                    WHERE username = %s AND id_concurs IN %s
                """, (new_username, tuple(contests_to_remove)))

            for contest_id in contests_to_add:
                cursor.execute("""
                    INSERT INTO participanti_concurs (id_concurs, username)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                """, (contest_id, new_username))

            conn.commit()
            flash("Concurentul a fost actualizat cu succes!", "success")
            return redirect(url_for("view_contestants"))

        else:
            cursor.execute("SELECT id, username, user_type, nume_prenume FROM concurenti WHERE id = %s", (id,))
            contestant = cursor.fetchone()

            if not contestant:
                flash("Concurentul nu a fost găsit!", "danger")
                return redirect(url_for("view_contestants"))

            cursor.execute("SELECT id_concurs, titlu FROM concurs")
            contests = cursor.fetchall()

            cursor.execute("SELECT id_concurs FROM participanti_concurs WHERE username = %s", (contestant[1],))
            assigned_contests = [row[0] for row in cursor.fetchall()]

            cursor.execute("SELECT DISTINCT id_concurs FROM participanti_scoruri WHERE username = %s", (contestant[1],))
            completed_contests = [row[0] for row in cursor.fetchall()]

            return render_template(
                "edit_contestant.html",
                contestant=contestant,
                contests=contests,
                assigned_contests=assigned_contests,
                completed_contests=completed_contests,
                username=username,
            )

    except (Exception, psycopg2.Error) as error:
        if conn:
            conn.rollback()
        print("Eroare la actualizarea concurentului:", error)
        flash(f"A intervenit o eroare în timpul actualizării concurentului: {error}", "danger")
        return redirect(url_for("edit_contestant", id=id))

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()



@app.route("/delete_contestant/<int:id>")
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def delete_contestant(id):
    try:
        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute("SELECT username FROM concurenti WHERE id = %s", (id,))
        username = cursor.fetchone()

        if username:
            username = username[0]

            cursor.execute(
                "DELETE FROM participanti_raspuns WHERE username = %s", (username,)
            )
            cursor.execute(
                "DELETE FROM participanti_concurs WHERE username = %s", (username,)
            )
            cursor.execute(
                "DELETE FROM participanti_scoruri WHERE username = %s", (username,)
            )

            cursor.execute("DELETE FROM concurenti WHERE id = %s", (id,))

            connection.commit()
            flash("Concurentul a fost șters cu succes!", "success")
        else:
            flash("Concurentul nu a fost găsit.", "danger")

    except (Exception, psycopg2.Error) as error:
        print("Eroare la ștergere:", error)
        connection.rollback()
        flash(f"A apărut o eroare în timpul ștergerii: {error}", "danger")

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()

    return redirect(url_for("view_contestants"))


@app.route("/menu")
@authenticate
def menu():
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    user_type = session["user_type"]

    assigned_contests = []
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="0",
            port="5432",
            database="postgres",
        )
        cursor = connection.cursor()

        if user_type == "concurent":
            cursor.execute(
                """
                SELECT DISTINCT pc.id_concurs, c.titlu 
                FROM participanti_concurs pc
                JOIN concurs c ON pc.id_concurs = c.id_concurs
                WHERE pc.username = %s
            """,
                (username,),
            )
            assigned_contests = cursor.fetchall()

            if not assigned_contests:
                flash("Nu sunteți asignat la niciun concurs.", "danger")

    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea concursurilor atribuite:", error)
        flash(
            f"A intervenit o eroare în timpul preluării concursurilor atribuite: {error}",
            "danger",
        )

    finally:
        if connection:
            cursor.close()
            connection.close()

    return render_template(
        "menu.html",
        username=username,
        user_type=user_type,
        assigned_contests=assigned_contests,
    )


@app.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("user_type", None)
    g.current_user = None
    return redirect(url_for("login"))


@app.route("/view_contests", methods=["GET", "POST"])
@authorize(['admin', 'hr', 'contribuitor'])
@authenticate

def view_contests():
    username = session["username"]
    user_type = session["user_type"]
    contests = []
    search_query = request.args.get("query", "").lower()
    column = request.args.get("column", "data_ora")
    order = request.args.get("order", "asc")
    current_date = datetime.now()

    column_mapping = {
        "id_concurs": "c.id_concurs",
        "titlu": "c.titlu",
        "sucursala": "c.sucursala",
        "departament": "c.departament",
        "data_ora": "c.data_ora",
        "participants": "participant_count",
        "nume_set": "s.nume_set",
    }

    if column not in column_mapping:
        column = "data_ora"

    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="0",
            port="5432",
            database="postgres",
        )
        cursor = connection.cursor()

        
        query = """
            SELECT c.id_concurs, c.titlu, c.sucursala, c.departament, c.data_ora, 
                   ARRAY_AGG(p.username) AS participants, 
                   COUNT(p.username) AS participant_count, 
                   COALESCE(s.nume_set, 'N/A') AS nume_set
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
                OR LOWER(COALESCE(s.nume_set, '')) LIKE %s
                OR CAST(c.data_ora AS TEXT) LIKE %s
                OR CAST(c.id_concurs AS TEXT) LIKE %s
            """
            search_param = f"%{search_query}%"
            params = [
                search_param, search_param, search_param, 
                search_param, search_param, search_param, search_param
            ]
        else:
            params = []



        query += f" GROUP BY c.id_concurs, s.nume_set ORDER BY {column_mapping[column]} {'ASC' if order == 'asc' else 'DESC'}"
        cursor.execute(query, tuple(params))
        contests = cursor.fetchall()

        contests_data = []
        for contest in contests:
            participants = []
            for participant in contest[5]:
                cursor.execute(
                    "SELECT id_set, scor_total FROM participanti_scoruri WHERE id_concurs = %s AND username = %s",
                    (contest[0], participant),
                )
                rows = cursor.fetchall()
                variants = []
                for row in rows:
                    variants.append(
                        {
                            "id_set": row[0],
                            "total_score": row[1],
                            "title": "Standard"
                            if len(variants) == 0
                            else "Rezerva",
                            "completed": row[1] is not None,
                        }
                    )
                participants.append({
                    "username": participant,
                    "variants": variants,
                })

            contests_data.append(
                {
                    "id_concurs": contest[0],
                    "titlu": contest[1],
                    "sucursala": contest[2],
                    "departament": contest[3],
                    "data_ora": contest[4],
                    "participants": participants,
                    "nume_set": contest[7],
                }
            )
        
    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea datelor din PostgreSQL", error)
    finally:
        if connection:
            cursor.close()
            connection.close()

    has_contests = len(contests_data) > 0

    return render_template(
        "view_contests.html",
        username=username,
        user_type=user_type,
        contests=contests_data,
        has_contests=has_contests,
        column=column,
        order=order,
        current_date=current_date
    )



@app.route("/create_question_set", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def create_question_set():
    username = session["username"]

    if request.method == "POST":
        id_set = request.form.get("id_set")
        nume_set = request.form.get("nume_set")

        if not id_set or not nume_set:
            flash("Toate câmpurile sunt obligatorii.", "danger")
            return redirect(url_for("create_question_set"))

        try:
            connection = psycopg2.connect(
                user="postgres",
                password="vasilica",
                host="0",
                port="5432",
                database="postgres",
            )
            cursor = connection.cursor()

            # Check if the id_set already exists
            cursor.execute(
                "SELECT id_set FROM seturi_intrebari WHERE id_set = %s", (id_set,)
            )
            existing_id = cursor.fetchone()
            if existing_id:
                flash(
                    "ID-ul setului de întrebări există deja! Te rugăm să alegi altul.",
                    "danger",
                )
                return redirect(url_for("create_question_set"))

            # Insert the new question set
            cursor.execute(
                """
                INSERT INTO seturi_intrebari (id_set, nume_set)
                VALUES (%s, %s)
            """,
                (id_set, nume_set),
            )

            for i in range(18):  # Iterate through 18 questions
                question_text = re.sub(
                    "\s+", " ", request.form.get(f"questions[{i}][question]")
                )
                answer_count = int(request.form.get(f"questions[{i}][answer_count]"))

                if not question_text:
                    continue  # Skip empty questions

                # Insert question
                cursor.execute(
                    """
                    INSERT INTO intrebari (id_set, intrebare, is_used)
                    VALUES (%s, %s, %s)
                    RETURNING id_intrebare
                """,
                    (id_set, question_text, False),
                )
                id_intrebare = cursor.fetchone()[0]

                # Insert answers
                for j in range(answer_count):
                    raspuns = re.sub(
                        "\s+",
                        " ",
                        request.form.get(f"questions[{i}][answers][{j}][answer]"),
                    )
                    punctaj = int(
                        request.form.get(f"questions[{i}][answers][{j}][score]")
                    )

                    if raspuns:
                        cursor.execute(
                            """
                            INSERT INTO raspunsuri (id_intrebare, raspuns, punctaj)
                            VALUES (%s, %s, %s)
                        """,
                            (id_intrebare, raspuns, punctaj),
                        )

            connection.commit()
            return redirect(url_for("view_question_sets"))

        except (Exception, psycopg2.Error) as error:
            print("Eroare la crearea setului de întrebări:", error)
            flash(
                f"A intervenit o eroare în timpul creării setului de întrebări: {error}",
                "danger",
            )
            return redirect(url_for("create_question_set"))

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()
    else:
        connection = connect_db()
        cursor = connection.cursor()
        # Fetch existing ids
        cursor.execute("SELECT id_set FROM seturi_intrebari")
        existing_ids = [e for (e,) in cursor.fetchall()]

    contests = get_contests()

    return render_template(
        "create_question_set.html",
        question_set={},
        contests=contests,
        username=username,
        existing_ids=existing_ids,
    )


def get_contests():
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="0",
            port="5432",
            database="postgres",
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


@app.route("/create_contest", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def create_contest():
    username = session.get("username")

    if request.method == "POST":
        id_concurs = request.form.get("id_concurs")
        title = request.form.get("title")
        branch = request.form.get("branch")
        department = request.form.get("department")
        datetime = request.form.get("datetime")
        participants = request.form.getlist("participants")
        id_set = request.form.get("id_set")

        if not all([id_concurs, title, branch, department, datetime, id_set]):
            flash("Toate câmpurile sunt obligatorii.", "danger")
            return redirect(url_for("create_contest"))

        try:
            connection = connect_db()
            cursor = connection.cursor()

            # Check whether id_concurs already exists and error out
            cursor.execute(
                "SELECT id_concurs FROM concurs WHERE id_concurs = %s", (id_concurs,)
            )
            existing_id = cursor.fetchone()

            if existing_id:
                flash(
                    "ID-ul concursului există deja! Te rugăm să alegi altul.", "danger"
                )
                return redirect(url_for("create_contest"))

            # Get the latest version of a set
            cursor.execute(
                """
                SELECT id_set
                FROM seturi_intrebari
                WHERE parent_id = %s
                ORDER BY version DESC
                LIMIT 1
                """,
                (id_set,),
            )
            result = cursor.fetchone()
            # In case there are no versions, we only have the base set, so keep it
            id_set = result[0] if result is not None else id_set

            # Get random questions from the given set
            cursor.execute(
                """
                SELECT id_intrebare FROM intrebari
                WHERE id_set = %s AND NOT is_used
                ORDER BY random()
                """,
                (id_set,),
            )
            available_questions = cursor.fetchall()

            # Get number of questions in the set
            cursor.execute(
                """
                SELECT COUNT(*) FROM intrebari
                WHERE id_set = %s
                """,
                (id_set,),
            )
            total_questions = cursor.fetchone()[0]
            if len(available_questions) < 6 and total_questions < 6:
                flash(
                    "Setul de întrebări nu are suficiente întrebări disponibile (minim 6).",
                    "danger",
                )
                return redirect(url_for("create_contest"))
            elif len(available_questions) < 6:
                # Reset used status for all questions in the set
                cursor.execute(
                    """
                    UPDATE intrebari
                    SET is_used = false
                    WHERE id_set = %s
                    """,
                    (id_set,),
                )
                # Get all questions again
                cursor.execute(
                    """
                        SELECT id_intrebare FROM intrebari
                        WHERE id_set = %s AND NOT is_used
                        ORDER BY random()
                    """,
                    (id_set,),
                )
                available_questions = cursor.fetchall()

            # Set 3 random questions for each of the quizzes
            quiz1_questions = available_questions[:9]
            quiz2_questions = available_questions[9:18]

            # Add contest
            cursor.execute(
                """
                INSERT INTO concurs (id_concurs, titlu, sucursala, departament, data_ora)
                VALUES (%s, %s, %s, %s, %s)
            """,
                (id_concurs, title, branch, department, datetime),
            )

            # Add the contest to each participant
            for participant in participants:
                cursor.execute(
                    """
                    INSERT INTO participanti_concurs (id_concurs, username)
                    VALUES (%s, %s)
                """,
                    (id_concurs, participant),
                )

            # Create questionnaire
            cursor.execute(
                """
                INSERT INTO chestionare (id_concurs, numar_chestionar, tip, id_set)
                VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
            """,
                (id_concurs, 1, "standard", id_set, id_concurs, 2, "rezerva", id_set),
            )

            # Get questionnaire IDs
            cursor.execute(
                """
                SELECT id_chestionar, tip FROM chestionare
                WHERE id_concurs = %s
            """,
                (id_concurs,),
            )
            quiz_ids = cursor.fetchall()
            quiz1_id = next(id for id, tip in quiz_ids if tip == "standard")
            quiz2_id = next(id for id, tip in quiz_ids if tip == "rezerva")

            # Add questions to standard set
            for question_id in quiz1_questions:
                cursor.execute(
                    """
                    INSERT INTO chestionar_intrebari (id_chestionar, id_intrebare)
                    VALUES (%s, %s)
                """,
                    (quiz1_id, question_id[0]),
                )

            # Add questions to reserve set
            for question_id in quiz2_questions:
                cursor.execute(
                    """
                    INSERT INTO chestionar_intrebari (id_chestionar, id_intrebare)
                    VALUES (%s, %s)
                """,
                    (quiz2_id, question_id[0]),
                )

            # Mark used questions
            cursor.execute(
                """
                UPDATE intrebari
                SET is_used = true
                WHERE id_intrebare IN %s
            """,
                (tuple([q[0] for q in quiz1_questions + quiz2_questions]),),
            )

            # Check whether we have remaining questions
            cursor.execute(
                """
                SELECT COUNT(*) FROM intrebari WHERE id_set = %s AND is_used = FALSE
            """,
                (id_set,),
            )
            remaining_questions = cursor.fetchone()[0]

            # Reset questions
            if remaining_questions == 0:
                cursor.execute(
                    """
                    UPDATE intrebari
                    SET is_used = FALSE
                    WHERE id_set = %s
                """,
                    (id_set,),
                )

            # Add contest and set to concursuri_seturi
            cursor.execute(
                """
                INSERT INTO concursuri_seturi (id_concurs, id_set)
                VALUES (%s, %s)
                ON CONFLICT (id_concurs, id_set) DO UPDATE
                SET id_set = EXCLUDED.id_set
            """,
                (id_concurs, id_set),
            )

            connection.commit()

            return redirect(url_for("view_contests"))

        except (Exception, psycopg2.Error) as error:
            print("Eroare la crearea concursului:", error)
            flash(
                f"A intervenit o eroare în timpul creării concursului: {error}",
                "danger",
            )
            return redirect(url_for("create_contest"))

        finally:
            if connection:
                cursor.close()
                connection.close()

    try:
        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute("SELECT DISTINCT sucursala FROM organizare")
        branches = [row[0] for row in cursor.fetchall()]

        cursor.execute("SELECT sucursala, departament FROM organizare")
        organizare = cursor.fetchall()

        cursor.execute("SELECT username FROM concurenti ORDER BY username ASC")
        participants = [row[0] for row in cursor.fetchall()]

        cursor.execute(
            "SELECT id_set, nume_set FROM seturi_intrebari WHERE parent_id IS NULL"
        )
        question_sets = cursor.fetchall()

        cursor.execute("SELECT id_concurs FROM concurs")
        existing_ids = [e for (e,) in cursor.fetchall()]

    except (Exception, psycopg2.Error) as error:
        print("Eroare la accesarea bazei de date:", error)
        flash(
            f"A intervenit o eroare în timpul accesării bazei de date: {error}",
            "danger",
        )
        return redirect(url_for("create_contest"))

    finally:
        if connection:
            cursor.close()
            connection.close()

    return render_template(
        "create_contest.html",
        username=username,
        branches=branches,
        organizare=organizare,
        participants=participants,
        question_sets=question_sets,
        existing_ids=existing_ids,
    )


@app.route("/preview_quizzes/<id_concurs>", methods=["GET"])
@authenticate
@authorize(['admin', 'hr'])
def preview_quizzes(id_concurs):
    username = session.get("username")
    try:
        connection = psycopg2.connect(
            user="postgres",
            password="vasilica",
            host="0",
            port="5432",
            database="postgres",
        )
        cursor = connection.cursor()

        # Fetch quizzes for the contest
        cursor.execute(
            """
            SELECT numar_chestionar, tip FROM chestionare
            WHERE id_concurs = %s
        """,
            (id_concurs,),
        )
        quizzes = cursor.fetchall()

        # Initialize quiz data
        quiz_data = {}
        for numar_chestionar, tip in quizzes:
            # Fetch questions for each quiz
            cursor.execute(
                """
                SELECT id_intrebare, intrebare FROM intrebari
                WHERE id_intrebare IN (
                    SELECT id_intrebare FROM chestionar_intrebari
                    WHERE id_chestionar = (
                        SELECT id_chestionar FROM chestionare
                        WHERE id_concurs = %s AND numar_chestionar = %s
                    )
                )
            """,
                (id_concurs, numar_chestionar),
            )
            questions = cursor.fetchall()

            # Fetch answers for each question
            questions_with_answers = []
            for id_intrebare, intrebare in questions:
                cursor.execute(
                    """
                    SELECT raspuns FROM raspunsuri
                    WHERE id_intrebare = %s
                """,
                    (id_intrebare,),
                )
                answers = cursor.fetchall()
                questions_with_answers.append(
                    {"intrebare": intrebare, "raspunsuri": [ans[0] for ans in answers]}
                )

            quiz_data[numar_chestionar] = questions_with_answers

    except (Exception, psycopg2.Error) as error:
        print("Eroare la vizualizarea chestionarelor:", error)
        flash(
            f"A intervenit o eroare în timpul vizualizării chestionarelor: {error}",
            "danger",
        )
        return redirect(url_for("create_contest"))

    finally:
        if connection:
            cursor.close()
            connection.close()

    return render_template(
        "preview_quizzes.html",
        id_concurs=id_concurs,
        quizzes=dict(quizzes),
        quiz_data=quiz_data,
        username=username,
    )


@app.route("/edit_contest/<old_id_concurs>", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def edit_contest(old_id_concurs):
    username = session.get("username")

    if request.method == "POST":
        new_id_concurs = request.form.get("id_concurs")
        title = request.form.get("title")
        branch = request.form.get("branch") or None  # If empty, set to None
        department = request.form.get("department") or None  # If empty, set to None
        datetime = request.form.get("datetime")
        participants = request.form.getlist("participants")
        id_set = request.form.get("id_set")

        conn = connect_db()
        cursor = conn.cursor()

        try:
            cursor.execute("BEGIN")

            # Check if the new `id_concurs` already exists and is not the same as the old one
            if new_id_concurs:
                cursor.execute(
                    "SELECT id_concurs FROM concurs WHERE id_concurs = %s",
                    (new_id_concurs,),
                )
                if cursor.fetchone() and old_id_concurs != new_id_concurs:
                    flash(
                        f"ID-ul concursului {new_id_concurs} este deja utilizat. Te rugăm să alegi alt ID.",
                        "danger",
                    )
                    conn.rollback()
                    return redirect(
                        url_for("edit_contest", old_id_concurs=old_id_concurs)
                    )
                elif new_id_concurs != old_id_concurs:
                    cursor.execute(
                        "UPDATE concurs SET id_concurs = %s WHERE id_concurs = %s",
                        (new_id_concurs, old_id_concurs),
                    )

                    # id was changed, so we do this to simplify control flow
                    old_id_concurs = new_id_concurs

            # Retrieve the current set ID associated with the old contest
            cursor.execute(
                "SELECT id_set FROM concursuri_seturi WHERE id_concurs = %s",
                (old_id_concurs,),
            )
            current_set_row = cursor.fetchone()
            current_set = current_set_row[0] if current_set_row else None

            if title:
                cursor.execute(
                    "UPDATE concurs SET titlu = %s WHERE id_concurs = %s",
                    (title, old_id_concurs),
                )
            if department:
                cursor.execute(
                    "UPDATE concurs SET departament = %s WHERE id_concurs = %s",
                    (department, old_id_concurs),
                )
            if branch:
                cursor.execute(
                    "UPDATE concurs SET sucursala = %s WHERE id_concurs = %s",
                    (branch, old_id_concurs),
                )
            if datetime:
                cursor.execute(
                    "UPDATE concurs SET data_ora = %s WHERE id_concurs = %s",
                    (datetime, old_id_concurs),
                )

            # Handle the record in `concursuri_seturi`
            if id_set != "none" and id_set is not None:
                cursor.execute(
                    "DELETE FROM concursuri_seturi WHERE id_concurs = %s",
                    (old_id_concurs,),
                )

                cursor.execute(
                    """
                    INSERT INTO concursuri_seturi (id_concurs, id_set)
                    VALUES (%s, %s)
                """,
                    (old_id_concurs, id_set),
                )

                # Update quizzes only if the set has changed
                if str(current_set) != str(id_set):  # Comparăm ca stringuri
                    cursor.execute(
                        "DELETE FROM chestionar_intrebari WHERE id_chestionar IN (SELECT id_chestionar FROM chestionare WHERE id_concurs = %s)",
                        (old_id_concurs,),
                    )
                    cursor.execute(
                        "DELETE FROM chestionare WHERE id_concurs = %s",
                        (old_id_concurs,),
                    )

                    # Reset is_used for the old set questions if it was used
                    if current_set:
                        cursor.execute(
                            """
                            UPDATE intrebari
                            SET is_used = FALSE
                            WHERE id_set = %s
                        """,
                            (current_set,),
                        )

                    cursor.execute(
                        """
                        SELECT id_intrebare FROM intrebari
                        WHERE id_set = %s
                        ORDER BY random()
                    """,
                        (id_set,),
                    )
                    questions = cursor.fetchall()

                    if len(questions) < 18:
                        flash(
                            "Setul de întrebări nu are suficiente întrebări (minim 18).",
                            "danger",
                        )
                        return redirect(
                            url_for("edit_contest", old_id_concurs=old_id_concurs)
                        )

                    quiz1_questions = questions[:9]
                    quiz2_questions = questions[9:18]

                    cursor.execute(
                        """
                        INSERT INTO chestionare (id_concurs, numar_chestionar, tip, id_set)
                        VALUES (%s, %s, %s, %s), (%s, %s, %s, %s)
                    """,
                        (
                            old_id_concurs,
                            1,
                            "standard",
                            id_set,
                            old_id_concurs,
                            2,
                            "rezerva",
                            id_set,
                        ),
                    )

                    cursor.execute(
                        """
                        SELECT id_chestionar, tip FROM chestionare
                        WHERE id_concurs = %s
                    """,
                        (old_id_concurs,),
                    )
                    quiz_ids = cursor.fetchall()
                    quiz1_id = next(id for id, tip in quiz_ids if tip == "standard")
                    quiz2_id = next(id for id, tip in quiz_ids if tip == "rezerva")

                    for question_id in quiz1_questions:
                        cursor.execute(
                            """
                            INSERT INTO chestionar_intrebari (id_chestionar, id_intrebare)
                            VALUES (%s, %s)
                        """,
                            (quiz1_id, question_id[0]),
                        )

                    for question_id in quiz2_questions:
                        cursor.execute(
                            """
                            INSERT INTO chestionar_intrebari (id_chestionar, id_intrebare)
                            VALUES (%s, %s)
                        """,
                            (quiz2_id, question_id[0]),
                        )

                    # Mark new questions as used
                    cursor.execute(
                        """
                        UPDATE intrebari
                        SET is_used = TRUE
                        WHERE id_set = %s AND id_intrebare IN %s
                    """,
                        (id_set, tuple(q[0] for q in questions)),
                    )

            cursor.execute(
                "SELECT username FROM participanti_concurs WHERE id_concurs = %s",
                (old_id_concurs,),
            )
            current_participants = {row[0] for row in cursor.fetchall()}

            cursor.execute(
                "SELECT DISTINCT username FROM participanti_scoruri WHERE id_concurs = %s",
                (old_id_concurs,),
            )
            completed_participants = {row[0] for row in cursor.fetchall()}

            participants_to_remove = (
                current_participants - set(participants) - completed_participants
            )
            participants_to_add = set(participants) - current_participants

            # Handle participants
            if participants_to_remove:
                for participant in participants_to_remove:
                    cursor.execute(
                        "DELETE FROM participanti_concurs WHERE username = %s AND id_concurs = %s",
                        (
                            participant,
                            old_id_concurs,
                        ),
                    )
            if participants_to_add:
                for participant in participants_to_add:
                    cursor.execute(
                        "INSERT INTO participanti_concurs (id_concurs, username) VALUES (%s, %s)",
                        (old_id_concurs, participant),
                    )

            conn.commit()
            flash("Concursul a fost actualizat cu succes!", "success")
        except Exception as e:
            conn.rollback()
            flash(
                f"Concursul nu poate fi modificat: {e}",
                "danger",
            )
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for("view_contests"))

    else:
        conn = connect_db()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT * FROM concurs WHERE id_concurs = %s", (old_id_concurs,)
            )
            contest = cursor.fetchone()
            if not contest:
                flash("Concursul nu a fost găsit!", "danger")
                return redirect(url_for("view_contests"))

            cursor.execute("SELECT sucursala, departament FROM organizare")
            organizare = cursor.fetchall()

            cursor.execute("SELECT username FROM concurenti ORDER BY username ASC")
            available_participants = [row[0] for row in cursor.fetchall()]

            # Only get base versions of the sets
            cursor.execute(
                "SELECT id_set, nume_set FROM seturi_intrebari WHERE parent_id IS NULL"
            )
            question_sets = cursor.fetchall()

            cursor.execute(
                "SELECT username FROM participanti_concurs WHERE id_concurs = %s",
                (old_id_concurs,),
            )
            selected_participants = [row[0] for row in cursor.fetchall()]

            cursor.execute(
                "SELECT DISTINCT username FROM participanti_scoruri WHERE id_concurs = %s",
                (old_id_concurs,),
            )
            completed = len(cursor.fetchall()) > 0

            cursor.execute(
                """
                SELECT COALESCE(parent_id, cs.id_set) FROM concursuri_seturi cs
                JOIN seturi_intrebari si ON cs.id_set = si.id_set
                WHERE id_concurs = %s
                """,
                (old_id_concurs,),
            )
            selected_set_row = cursor.fetchone()
            selected_set = selected_set_row[0] if selected_set_row else "none"

            branches_departments = [(item[0], item[1]) for item in organizare]
            branches = list(set([item[0] for item in branches_departments]))

            cursor.execute("SELECT id_concurs FROM concurs")
            existing_ids = [e for (e,) in cursor.fetchall()]

            return render_template(
                "edit_contest.html",
                contest=contest,
                branches=branches,
                branches_departments=branches_departments,
                available_participants=available_participants,
                selected_participants=selected_participants,
                question_sets=question_sets,
                selected_set=selected_set,
                username=username,
                completed=completed,
                existing_ids=existing_ids,
            )

        except Exception as e:
            flash(
                f"A intervenit o eroare în timpul accesării bazei de date: {str(e)}",
                "danger",
            )
            return redirect(url_for("view_contests"))
        finally:
            cursor.close()
            conn.close()


@app.route("/delete_contest/<id_concurs>", methods=["GET"])
@authenticate
@authorize(['admin', 'hr'])
def delete_contest(id_concurs):
    try:
        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute(
            "DELETE FROM concursuri_seturi WHERE id_concurs = %s", (id_concurs,)
        )

        cursor.execute(
            "DELETE FROM participanti_concurs WHERE id_concurs = %s", (id_concurs,)
        )

        cursor.execute("DELETE FROM concurs WHERE id_concurs = %s", (id_concurs,))

        connection.commit()
        flash("Concursul a fost șters cu succes!", "success")
        return redirect(url_for("view_contests"))

    except (Exception, psycopg2.Error) as error:
        print("Eroare la ștergerea concursului:", error)
        flash(
            f"A intervenit o eroare în timpul ștergerii concursului, deoarece acesta a fost parcurs deja.", "danger"
        )
        return redirect(url_for("view_contests"))

    finally:
        if connection:
            cursor.close()
            connection.close()


@app.route("/view_question_sets", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def view_question_sets():
    user_type = session["user_type"]
    username = session["username"]
    question_sets = []
    search_term = request.args.get("search_term", "")
    column = request.args.get("column", "id_set")
    order = request.args.get("order", "asc")

    print(f"Search term: {search_term}, Column: {column}, Order: {order}")

    try:
        connection = connect_db()
        cursor = connection.cursor()

        query = """
            SELECT si.id_set, si.nume_set, si.version
            FROM seturi_intrebari si
            LEFT JOIN seturi_intrebari children ON si.id_set = children.parent_id
            WHERE children.id_set IS NULL
        """

        if search_term:
            query += " AND LOWER(si.nume_set) LIKE %s"
            cursor.execute(query, (f"%{search_term.lower()}%",))
        else:
            cursor.execute(query)


        question_sets = cursor.fetchall()

    except psycopg2.Error as error:
        print("Eroare la preluarea seturilor de întrebări:", error)
    finally:
        if cursor:
            cursor.close()
        if connection:  
            connection.close()

    has_question_sets = bool(question_sets)
    return render_template(
        "view_question_sets.html",
        question_sets=question_sets,
        username=username,
        has_question_sets=has_question_sets,
        user_type=user_type,
    )



@app.route("/delete_question_set/<id_set>", methods=["GET"])
@authorize(['admin'])
def delete_question_set(id_set):
    if "username" not in session:
        return redirect(url_for("login"))
    try:
        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute("DELETE FROM concursuri_seturi WHERE id_set = %s", (id_set,))
        cursor.execute("DELETE FROM chestionare WHERE id_set = %s", (id_set,))

        cursor.execute(
            "DELETE FROM raspunsuri WHERE id_intrebare IN (SELECT id_intrebare FROM intrebari WHERE id_set = %s)",
            (id_set,),
        )
        cursor.execute("DELETE FROM intrebari WHERE id_set = %s", (id_set,))

        cursor.execute("DELETE FROM seturi_intrebari WHERE id_set = %s", (id_set,))

        connection.commit()
        flash("Setul de întrebări a fost șters cu succes!", "success")
        return redirect(url_for("view_question_sets"))
    except (Exception, Error) as error:
        print("Eroare la ștergerea setului:", error)
        flash(f"A intervenit o eroare în timpul ștergerii setului: {error}", "danger")
        return redirect(url_for("view_question_sets"))
    finally:
        if connection:
            cursor.close()
            connection.close()


@app.route("/edit_question_set/<id_set>", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def edit_question_set(id_set):
    username = session["username"]

    if request.method == "POST":
        new_name = re.sub(r"\s+", " ", request.form.get("nume_set"))

        if not new_name:
            flash("Toate câmpurile sunt obligatorii.", "danger")
            return redirect(url_for("edit_question_set", id_set=id_set))

        connection = None
        cursor = None

        try:
            connection = connect_db()
            cursor = connection.cursor()
            cursor.execute("BEGIN;")

            # Generate a new unique id_set for the new version
            cursor.execute("SELECT MAX(id_set) FROM seturi_intrebari")
            max_id_set = cursor.fetchone()[0] or 0
            new_id_set = max_id_set + 1

            # Get the latest version of the set
            cursor.execute(
            """
            SELECT MAX(version)
            FROM seturi_intrebari
            WHERE id_set = %s OR parent_id = %s
            """,
            (id_set, id_set),
        )
            result = cursor.fetchone()
            current_version = result[0] if result else 0

            
            # Insert a new version of the question set
            cursor.execute(
                """
                INSERT INTO seturi_intrebari (id_set, nume_set, version, parent_id)
                VALUES (%s, %s, %s, %s)
                """,
                (new_id_set, new_name, current_version + 1, id_set),
            )

            # Iterate through questions and update or insert them
            for i in range(18):
                question_text = re.sub(
                    "\s+", " ", request.form.get(f"questions[{i}][question]")
                )
                question_id = request.form.get(f"questions[{i}][id_intrebare]")
                answer_count = int(request.form.get(f"questions[{i}][answer_count]"))

                if question_text:
                    cursor.execute(
                        """
                        INSERT INTO intrebari (id_set, intrebare) 
                        VALUES (%s, %s) 
                        RETURNING id_intrebare
                        """,
                        (new_id_set, question_text),
                    )
                    question_id = cursor.fetchone()[0]

                    for j in range(answer_count):
                        raspuns = re.sub(
                            "\s+",
                            " ",
                            request.form.get(f"questions[{i}][answers][{j}][answer]"),
                        )
                        punctaj = int(
                            request.form.get(f"questions[{i}][answers][{j}][score]")
                        )

                        if raspuns:
                            cursor.execute(
                                """
                                INSERT INTO raspunsuri (id_intrebare, raspuns, punctaj)
                                VALUES (%s, %s, %s)
                            """,
                                (question_id, raspuns, punctaj),
                            )

            connection.commit()
            flash("Setul de întrebări a fost actualizat cu succes!", "success")
            return redirect(url_for("view_question_sets"))

        except (Exception, psycopg2.Error) as error:
            if connection:
                connection.rollback()
            flash(
                f"A intervenit o eroare în timpul actualizării setului de întrebări: {error}",
                "danger",
            )
            return redirect(url_for("edit_question_set", id_set=id_set))

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    else:
        try:
            connection = connect_db()
            cursor = connection.cursor()

            # Check if the selected set has versions
            cursor.execute(
                """
                SELECT id_set, nume_set
                FROM seturi_intrebari
                WHERE parent_id = %s
                ORDER BY version DESC
                LIMIT 1
                """,
                (id_set,),
            )
            question_set = cursor.fetchone()

            # No versions for the given set
            if question_set is None:
                # Fetch original question set details
                cursor.execute(
                    """
                    SELECT id_set, nume_set
                    FROM seturi_intrebari
                    WHERE id_set = %s
                    """,
                    (id_set,),
                )
                question_set = cursor.fetchone()

            # Fetch existing ids for validation
            cursor.execute("SELECT id_set FROM seturi_intrebari")
            existing_ids = [e[0] for e in cursor.fetchall()]

            # Fetch associated questions and answers
            cursor.execute(
                """
                SELECT id_intrebare, intrebare FROM intrebari WHERE id_set = %s ORDER BY id_intrebare ASC
                """,
                (question_set[0],),
            )
            questions = cursor.fetchall()

            question_details = []
            for question in questions:
                question_id, question_text = question
                cursor.execute(
                    """
                    SELECT raspuns, punctaj FROM raspunsuri WHERE id_intrebare = %s ORDER BY id_raspuns ASC
                    """,
                    (question_id,),
                )
                answers = cursor.fetchall()
                question_details.append(
                    {
                        "id_intrebare": question_id,
                        "intrebare": question_text,
                        "answers": [
                            {"raspuns": ans[0], "punctaj": ans[1]} for ans in answers
                        ],
                    }
                )

            # Send original id for the set, so that versioning can continue
            question_set = (id_set, question_set[1])

        except (Exception, psycopg2.Error) as error:
            flash(
                f"A intervenit o eroare în timpul preluării datelor: {error}", "danger"
            )
            return redirect(url_for("view_question_sets"))

        finally:
            if cursor:
                cursor.close()
            if connection:
                connection.close()

    return render_template(
        "edit_question_set.html",
        question_set=question_set,
        question_details=question_details,
        existing_ids=existing_ids,  # Keep this for client-side validation
        username=username,
    )


@app.route("/create_branch", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr'])
def create_branch():
    username = session.get("username")

    if request.method == "POST":
        branch = request.form["branch"]

        try:
            connection = connect_db()
            cursor = connection.cursor()

            cursor.execute("SELECT * FROM sucursale WHERE sucursala = %s", (branch,))
            existing_branch = cursor.fetchone()

            if existing_branch:
                flash("Această sucursală există deja!", "danger")
                return redirect(url_for("create_branch"))

            cursor.execute("INSERT INTO sucursale (sucursala) VALUES (%s)", (branch,))
            connection.commit()
            flash(f"Sucursala {branch} a fost adăugată cu succes!", "success")
            return redirect(url_for("view_branches"))

        except (Exception, psycopg2.Error) as error:
            print("Eroare la crearea sucursalei:", error)
            flash(
                f"A intervenit o eroare în timpul creării sucursalei: {error}", "danger"
            )
            return redirect(url_for("create_branch"))

        finally:
            if connection:
                cursor.close()
                connection.close()

    return render_template("create_branch.html", username=username)


@app.route("/create_department", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def create_department():
    username = session.get("username")

    if request.method == "POST":
        branch = request.form["branch"]
        departments = request.form.getlist("department[]")

        try:
            connection = connect_db()
            cursor = connection.cursor()

            for department in departments:
                cursor.execute(
                    "SELECT * FROM organizare WHERE sucursala = %s AND departament = %s",
                    (branch, department),
                )
                existing_department = cursor.fetchone()

                if existing_department:
                    flash(
                        f"Departamentul {department} există deja în sucursala {branch}!",
                        "danger",
                    )
                    return redirect(url_for("create_department"))

                cursor.execute(
                    "INSERT INTO organizare (sucursala, departament) VALUES (%s, %s)",
                    (branch, department),
                )

            connection.commit()
            flash("Departamentele au fost adăugate cu succes!", "success")
            return redirect(url_for("view_department"))

        except (Exception, psycopg2.Error) as error:
            print("Eroare la crearea departamentului:", error)
            flash(
                f"A intervenit o eroare în timpul creării departamentului: {error}",
                "danger",
            )
            return redirect(url_for("create_department"))

        finally:
            if connection:
                cursor.close()
                connection.close()

    else:
        try:
            connection = connect_db()
            cursor = connection.cursor()
            cursor.execute("SELECT sucursala FROM sucursale ORDER BY sucursala ASC")
            sucursale = cursor.fetchall()

        except (Exception, psycopg2.Error) as error:
            print("Eroare la preluarea sucursalelor:", error)
            flash(
                f"A intervenit o eroare în timpul preluării sucursalelor: {error}",
                "danger",
            )
            sucursale = []

        finally:
            if connection:
                cursor.close()
                connection.close()

    return render_template(
        "create_department.html", username=username, sucursale=sucursale
    )


@app.route("/edit_department/<sucursala>/<departament>", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def edit_department(sucursala, departament):
    username = session["username"]

    if request.method == "POST":
        new_department = request.form["department"]
        new_sucursala = request.form["sucursala"]

        try:
            connection = connect_db()
            cursor = connection.cursor()

            
            cursor.execute(
                """
                UPDATE organizare
                SET sucursala = %s, departament = %s
                WHERE sucursala = %s AND departament = %s
                """,
                (new_sucursala, new_department, sucursala, departament),
            )

            connection.commit()
            flash("Departamentul a fost actualizat cu succes!", "success")

        except psycopg2.Error as error:
            print("Eroare PostgreSQL:", error)
            flash(
                f"A intervenit o eroare în timpul actualizării departamentului: {error}",
                "danger",
            )
        finally:
            if connection:
                cursor.close()
                connection.close()

        return redirect(url_for("view_department"))

    else:
        try:
            connection = connect_db()
            cursor = connection.cursor()

            cursor.execute("SELECT sucursala FROM sucursale ORDER BY sucursala ASC")
            rows = cursor.fetchall()
            branches = [row[0] for row in rows]

        except psycopg2.Error as error:
            print("Eroare PostgreSQL:", error)
            flash(
                f"A intervenit o eroare în timpul preluării sucursalelor: {error}",
                "danger",
            )
        finally:
            if connection:
                cursor.close()
                connection.close()

        return render_template(
            "edit_department.html",
            username=username,
            sucursala=sucursala,
            departament=departament,
            branches=branches,
        )



@app.route("/view_department", methods=["GET"])
@authenticate
@authorize(['admin', 'hr', 'contribuitor'])
def view_department():
    username = session["username"]
    user_type = session["user_type"]
    branches = []
    search_query = request.args.get("query", "").lower()
    column = request.args.get("column", "sucursala")
    order = request.args.get("order", "asc")

    try:
        connection = connect_db()
        cursor = connection.cursor()

        if search_query:
            cursor.execute(
                f"""
                SELECT sucursala, departament
                FROM organizare
                WHERE LOWER(sucursala) LIKE %s
                OR LOWER(departament) LIKE %s
                ORDER BY {column} {order.upper()}
            """,
                (f"%{search_query}%", f"%{search_query}%"),
            )
        else:
            cursor.execute(
                f"SELECT sucursala, departament FROM organizare ORDER BY {column} {order.upper()}"
            )

        rows = cursor.fetchall()
        for row in rows:
            branches.append({"sucursala": row[0], "departament": row[1]})

    except psycopg2.Error as error:
        print("Eroare PostgreSQL:", error)
        flash(
            f"A intervenit o eroare în timpul preluării datelor despre sucursale și departamente: {error}",
            "danger",
        )
    finally:
        if connection:
            cursor.close()
            connection.close()
    has_branches = bool(branches)
    return render_template(
        "view_department.html",
        branches=branches,
        username=username,
        has_branches=has_branches,
        column=column,
        order=order,
        user_type=user_type,
    )


@app.route("/delete_department/<sucursala>/<departament>", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr'])
def delete_department(sucursala, departament):
    try:
        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute(
            """
            DELETE FROM organizare
            WHERE sucursala = %s AND departament = %s
        """,
            (sucursala, departament),
        )

        connection.commit()
        flash(f"Departamentul {departament} a fost șters cu succes.", "success")

    except psycopg2.Error as error:
        print("Eroare PostgreSQL:", error)
        flash(
            f"A intervenit o eroare în timpul ștergerii departamentului: {error}",
            "danger",
        )
    finally:
        if connection:
            cursor.close()
            connection.close()

    return redirect(url_for("view_department"))


@app.route("/view_branches", methods=["GET"])
@authorize(['admin', 'hr', 'contribuitor'])
@authenticate
def view_branches():
    username = session["username"]
    user_type = session["user_type"]
    branches = []
    search_query = request.args.get("query", "").lower()
    column = request.args.get("column", "sucursala")
    order = request.args.get("order", "asc")

    try:
        connection = connect_db()
        cursor = connection.cursor()

        if search_query:
            cursor.execute(
                f"""
                SELECT sucursala
                FROM sucursale
                WHERE LOWER(sucursala) LIKE %s
                ORDER BY {column} {order.upper()}
            """,
                (f"%{search_query}%",),
            )
        else:
            cursor.execute(
                f"SELECT sucursala FROM sucursale ORDER BY {column} {order.upper()}"
            )

        rows = cursor.fetchall()
        for row in rows:
            branches.append({"sucursala": row[0]})

    except psycopg2.Error as error:
        print("Eroare PostgreSQL:", error)
        flash(
            f"A intervenit o eroare în timpul preluării sucursalelor: {error}", "danger"
        )
    finally:
        if connection:
            cursor.close()
            connection.close()
    has_branches = bool(branches)
    return render_template(
        "view_branches.html",
        branches=branches,
        username=username,
        has_branches=has_branches,
        column=column,
        order=order,
        user_type=user_type,
    )


@app.route("/edit_branch/<sucursala>", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr'])
def edit_branch(sucursala):
    username = session["username"]

    if request.method == "POST":
        new_sucursala = request.form["sucursala"]

        try:
            connection = connect_db()
            cursor = connection.cursor()

            cursor.execute(
                """
                UPDATE sucursale
                SET sucursala = %s
                WHERE sucursala = %s
            """,
                (new_sucursala, sucursala),
            )

            cursor.execute(
                """
                UPDATE concurs
                SET sucursala = %s
                WHERE sucursala = %s AND id_concurs NOT IN (SELECT id_concurs FROM participanti_scoruri)
            """,
                (new_sucursala, sucursala),
            )

            cursor.execute(
                """
                UPDATE organizare
                SET sucursala = %s
                WHERE sucursala = %s
            """,
                (new_sucursala, sucursala),
            )

            connection.commit()
            flash(f"Sucursala {sucursala} a fost actualizată cu succes!", "success")

        except psycopg2.Error as error:
            print("Eroare PostgreSQL:", error)
            flash(
                f"A intervenit o eroare în timpul actualizării sucursalei: {error}",
                "danger",
            )
        finally:
            if connection:
                cursor.close()
                connection.close()

        return redirect(url_for("view_branches"))

    else:
        return render_template(
            "edit_branch.html", username=username, sucursala=sucursala
        )


@app.route("/delete_branch/<sucursala>", methods=["POST"])
@authenticate
@authorize(['admin', 'hr'])
def delete_branch(sucursala):
    try:
        connection = connect_db()
        cursor = connection.cursor()

        # Set sucursala to NULL or 'None' in related tables before deletion
        cursor.execute(
            """
            UPDATE concurs
            SET sucursala = NULL  -- or 'None'
            WHERE sucursala = %s
        """,
            (sucursala,),
        )

        cursor.execute(
            """
            UPDATE organizare
            SET sucursala = NULL  -- or 'None'
            WHERE sucursala = %s
        """,
            (sucursala,),
        )

        # Delete the branch from sucursale table
        cursor.execute(
            """
            DELETE FROM sucursale
            WHERE sucursala = %s
        """,
            (sucursala,),
        )

        connection.commit()
        flash(f"Sucursala {sucursala} a fost ștearsă cu succes!", "success")

    except psycopg2.Error as error:
        print("Eroare PostgreSQL:", error)
        flash(
            f"A intervenit o eroare în timpul ștergerii sucursalei: {error}", "danger"
        )
    finally:
        if connection:
            cursor.close()
            connection.close()

    return redirect(url_for("view_branches"))


@app.route("/view_test/<int:id_set>", methods=["GET", "POST"])
def view_test(id_set):
    username = session["username"]
    try:
        connection = connect_db()
        cursor = connection.cursor()

        id_concurs = request.args.get("id_concurs")

        if not id_concurs or not id_concurs.isdigit():
            flash("Id-ul concursului lipsește sau nu este valid.", "danger")
            return redirect(url_for("view_question_sets"))

        username = session["username"]
        cursor.execute(
            "SELECT 1 FROM participanti_concurs WHERE username = %s AND id_concurs = %s",
            (username, id_concurs),
        )
        user_is_participant = cursor.fetchone()

        if not user_is_participant:
            flash("Utilizatorul nu este participant la acest concurs.", "danger")
            return redirect(url_for("view_question_sets"))

        if request.method == "POST":
            print("Form data received:")
            print(request.form)
            answers = request.form.to_dict(flat=False)
            print("Answers dict:")
            print(answers)
            for q_id, answer_ids in answers.items():
                if answer_ids and q_id.startswith("question_"):
                    q_id = q_id.split("_")[1]  # Extract the actual question ID
                    for answer_id in answer_ids:
                        try:
                            numeric_answer_id = int(
                                "".join(filter(str.isdigit, str(answer_id)))
                            )
                            print(
                                f"Inserting answer for question {q_id}, answer_id {numeric_answer_id}"
                            )
                            cursor.execute(
                                """
                                INSERT INTO participanti_raspuns (username, id_concurs, id_intrebare, id_raspuns)
                                VALUES (%s, %s, %s, %s)
                            """,
                                (username, id_concurs, q_id, numeric_answer_id),
                            )
                        except ValueError:
                            print(f"Invalid answer ID: {answer_id} for question {q_id}")
                            continue  # Skip this answer and continue with the next

            connection.commit()
            flash("Testul a fost trimis cu succes!", "success")
            return redirect(url_for("view_question_sets"))

        cursor.execute(
            """
            SELECT i.id_intrebare, i.intrebare, r.id_raspuns, r.raspuns, r.punctaj
            FROM intrebari i
            LEFT JOIN raspunsuri r ON i.id_intrebare = r.id_intrebare
            WHERE i.id_set = %s
            ORDER BY i.id_intrebare
        """,
            (id_set,),
        )
        rows = cursor.fetchall()
        questions = {}

        for row in rows:
            question_id, question_text, answer_id, answer_text, score = row
            if question_id not in questions:
                questions[question_id] = {"question_text": question_text, "answers": []}
            if answer_id:
                questions[question_id]["answers"].append(
                    {"answer_id": answer_id, "answer_text": answer_text, "score": score}
                )

        return render_template(
            "view_test.html",
            questions=questions,
            id_set=id_set,
            id_concurs=id_concurs,
            username=username,
        )

    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea întrebărilor:", error)
        flash(
            f"A intervenit o eroare în timpul preluării întrebărilor: {error}", "danger"
        )
        return redirect(url_for("view_question_sets"))

    finally:
        if connection:
            cursor.close()
            connection.close()


@app.route("/solve_quiz/<int:id_chestionar>", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'concurent'])
def solve_quiz(id_chestionar):
    if "username" not in session:
        return redirect(url_for("login"))

    username = session["username"]
    if request.method == "POST":
        form = request.form
        id_concurs = request.form.get("id_concurs")
        end_time = request.form.get("end_time")
        print("received end_time", str(end_time))

        print(form)

        try:
            connection = connect_db()
            cursor = connection.cursor()
            questions_answers = dict()

            for key in form.items():
                if key[0].startswith("question_"):
                    question = int(key[0].split("_")[1].strip("[]"))
                    # raw answers
                    answers_raw = form.getlist(key[0])
                    # final clean answers
                    answers = [int(answer) for answer in answers_raw]
                    # add question and its answers to dict
                    questions_answers[question] = answers

            print(questions_answers)

            total_score = 10
            for question in questions_answers.keys():
                cursor.execute(
                    "SELECT id_raspuns, punctaj FROM raspunsuri WHERE id_intrebare = %s",
                    (question,),
                )
                answers_predefined = cursor.fetchall()
                answers_points = {answer[0]: answer[1] for answer in answers_predefined}
                answers_wrong = [
                    answer[0] for answer in answers_predefined if answer[1] == 0
                ]

                question_score = 0
                correct = True

                # for any incorrect answer selected (along with other correct ones), the score is 0
                if any(
                    answer in answers_wrong for answer in questions_answers[question]
                ):
                    correct = False

                for answer in questions_answers[question]:
                    question_score += answers_points[answer] if correct else 0

                    cursor.execute(
                        """
                        INSERT INTO participanti_raspuns (username, id_concurs, id_intrebare, id_raspuns, punctaj)
                        VALUES (%s, %s::VARCHAR, %s, %s, %s)
                    """,
                        (
                            username,
                            id_concurs,
                            question,
                            answer,
                            answers_points[answer] if correct else 0,
                        ),
                    )

                total_score += question_score

            cursor.execute(
                """
                SELECT 1 FROM participanti_scoruri WHERE username = %s AND id_concurs = %s AND id_set = %s
            """,
                (username, id_concurs, id_chestionar),
            )
            existing_score = cursor.fetchone()

            if existing_score:
                print("score already exists")
                # Check the existence of end_time
                cursor.execute(
                    """
                    SELECT end_time FROM participanti_scoruri
                    WHERE username = %s AND id_concurs = %s AND id_set = %s           
                """,
                    (username, id_concurs, id_chestionar),
                )
                result = cursor.fetchone()[0]

                # if it exists, don't resubmit the score
                if result is not None:
                    print("result is", result)
                    flash(
                        "Testul a fost terminat și nu mai poate fi accesat.", "danger"
                    )

                    # Get existing total score
                    cursor.execute(
                        """
                        SELECT scor_total FROM participanti_scoruri
                        WHERE username = %s AND id_concurs = %s AND id_set = %s           
                    """,
                        (username, id_concurs, id_chestionar),
                    )
                    total_score = cursor.fetchone()[0]

                    return redirect(
                        url_for(
                            "test_report",
                            id_concurs=id_concurs,
                            id_set=id_chestionar,
                            username=username,
                            total_score=total_score,
                        )
                    )

                cursor.execute(
                    """
                    UPDATE participanti_scoruri
                    SET scor_total = %s, end_time = (%s)
                    WHERE username = %s AND id_concurs = %s AND id_set = %s
                """,
                    (total_score, end_time, username, id_concurs, id_chestionar),
                )
                print("had existing score, updated scor_total and end_time")
            else:
                cursor.execute(
                    """
                    INSERT INTO participanti_scoruri (username, id_concurs, id_set, scor_total, end_time)
                    VALUES (%s, %s::VARCHAR, %s, %s, %s)
                """,
                    (username, id_concurs, id_chestionar, total_score, end_time),
                )
                print("created new entry with scor_total and end_time")

            cursor.execute(
                """
                INSERT INTO participanti_concurs (id_concurs, username, scor_total)
                VALUES (%s::VARCHAR, %s, %s)
                ON CONFLICT (id_concurs, username) 
                DO UPDATE SET scor_total = GREATEST(participanti_concurs.scor_total, %s)
            """,
                (id_concurs, username, total_score, total_score),
            )

            connection.commit()

            return redirect(
                url_for(
                    "test_report",
                    id_concurs=id_concurs,
                    id_set=id_chestionar,
                    username=username,
                    total_score=total_score,
                )
            )

        except (Exception, psycopg2.Error) as error:
            print("Eroare la salvarea răspunsurilor:", error)
            flash(f"A intervenit o eroare: {error}", "danger")
            return redirect(url_for("menu"))
        finally:
            if connection:
                cursor.close()
                connection.close()

    else:
        questions = {}
        current_time = datetime.now()
        contest_start_time = None

        try:
            connection = connect_db()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT id_concurs FROM chestionare WHERE id_chestionar = %s
            """,
                (id_chestionar,),
            )
            result = cursor.fetchone()
            if result is None:
                flash("Nu am găsit concursul asociat cu acest chestionar.", "danger")
                return redirect(url_for("menu"))

            id_concurs = result[0]

            # check whether table entry exists
            username = session["username"]
            cursor.execute(
                """
                SELECT 1 FROM participanti_scoruri WHERE username = %s AND id_concurs = %s AND id_set = %s
            """,
                (username, id_concurs, id_chestionar),
            )
            existing_entry = cursor.fetchone()

            # if it exists, get start_time and end_time
            if existing_entry:
                print("entry exists")
                # Check the existence of end_time
                cursor.execute(
                    """
                    SELECT end_time FROM participanti_scoruri
                    WHERE username = %s AND id_concurs = %s AND id_set = %s           
                """,
                    (username, id_concurs, id_chestionar),
                )
                result = cursor.fetchone()[0]

                # if it exists, don't allow the user to retake the test
                if result is not None:
                    print("result is", result)
                    flash(
                        "Testul a fost terminat și nu mai poate fi accesat.", "danger"
                    )
                    return redirect(url_for("menu"))

                # check start_time
                cursor.execute(
                    """
                    SELECT start_time FROM participanti_scoruri
                    WHERE username = %s AND id_concurs = %s AND id_set = %s
                """,
                    (username, id_concurs, id_chestionar),
                )
                result = cursor.fetchone()[0]

                # if start_time is not set, set it with the current time
                if result is None:
                    print("start_time not set")
                    contest_start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    cursor.execute(
                        """
                        UPDATE participanti_scoruri
                        SET start_time = (%s)
                        WHERE username = (%s) AND id_concurs = (%s) AND id_set = (%s);
                    """,
                        (str(contest_start_time), username, id_concurs, id_chestionar),
                    )
                    connection.commit()
                    print(
                        "setting start_time",
                        contest_start_time,
                        "for id_concurs",
                        id_concurs,
                        "and id_set",
                        id_chestionar,
                    )
                # if it exists and is set, get start_time
                else:
                    contest_start_time = result
                    print("start_time exists: ", contest_start_time)
                    print(current_time - contest_start_time)

                    # if current time is more than 2h ahead of contest_start_time, don't allow the user to take the test
                    if current_time - contest_start_time > timedelta(hours=2):
                        flash("Timpul alocat pentru concurs a expirat!", "error")
                        return redirect(url_for("menu"))

            # if it doesn't exist, add entry with start_time set
            else:
                print("entry does not exist, creating")
                contest_start_time = datetime.now()
                cursor.execute(
                    """
                    INSERT INTO participanti_scoruri (username, id_concurs, id_set, start_time)
                    VALUES (%s, %s::VARCHAR, %s, %s)
                """,
                    (username, id_concurs, id_chestionar, contest_start_time),
                )
                connection.commit()

            cursor.execute(
                """
                SELECT i.id_intrebare, i.intrebare, r.id_raspuns, r.raspuns
                FROM intrebari i
                JOIN raspunsuri r ON i.id_intrebare = r.id_intrebare
                WHERE i.id_intrebare IN (
                    SELECT id_intrebare FROM chestionar_intrebari WHERE id_chestionar = %s
                )
                ORDER BY i.id_intrebare, r.id_raspuns
            """,
                (id_chestionar,),
            )
            rows = cursor.fetchall()

            for row in rows:
                question_id, question_text, answer_id, answer_text = row
                if question_id not in questions:
                    questions[question_id] = {
                        "question_text": question_text,
                        "answers": [],
                    }
                questions[question_id]["answers"].append(
                    {"answer_id": answer_id, "answer_text": answer_text}
                )

            question_list = list(questions.items())
            random.shuffle(question_list)
            questions = dict(question_list)

            for question in questions.values():
                random.shuffle(question["answers"])

        except (Exception, psycopg2.Error) as error:
            print("Eroare la obținerea întrebărilor și răspunsurilor:", error)
            flash(f"A intervenit o eroare: {error}", "danger")
            return redirect(url_for("view_contest", id_concurs=id_concurs))

        finally:
            if connection:
                cursor.close()
                connection.close()

        return render_template(
            "solve_quiz.html",
            questions=questions,
            id_concurs=id_concurs,
            id_chestionar=id_chestionar,
            contest_start_time=contest_start_time,
            current_time=current_time,
        )


@app.route("/contest/<int:id_concurs>", methods=["GET"])
@authenticate
@authorize(['admin', 'concurent'])
def view_contest(id_concurs):
    if "username" not in session:
        return redirect(url_for("login"))

    quizzes = []
    standard_completed = False
    reserve_completed = False
    contest_start_time = None
    current_time = datetime.now()

    try:
        connection = connect_db()
        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT data_ora FROM concurs
            WHERE id_concurs = %s;
        """,
            (str(id_concurs),),
        )
        contest_start_time = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT id_chestionar, tip
            FROM chestionare
            WHERE id_concurs = %s::VARCHAR
            ORDER BY CASE WHEN tip = 'standard' THEN 1 ELSE 2 END;
        """,
            (str(id_concurs),),
        )
        quizzes = cursor.fetchall()

        cursor.execute(
            """
            SELECT COUNT(ps.id)
            FROM participanti_scoruri ps
            JOIN chestionare c ON ps.id_set = c.id_chestionar
            WHERE ps.username = %s AND ps.id_concurs = %s AND c.tip = 'standard';
        """,
            (session["username"], str(id_concurs)),
        )
        standard_completed = cursor.fetchone()[0] > 0
        print(standard_completed)
        cursor.execute(
            """
            SELECT COUNT(ps.id)
            FROM participanti_scoruri ps
            JOIN chestionare c ON ps.id_set = c.id_chestionar
            WHERE ps.username = %s AND ps.id_concurs = %s AND c.tip = 'rezerva';
        """,
            (session["username"], str(id_concurs)),
        )
        reserve_completed = cursor.fetchone()[0] > 0
        print(reserve_completed)
    except (Exception, psycopg2.Error) as error:
        print("Eroare la preluarea datelor:", error)
        flash(f"A intervenit o eroare: {error}", "danger")
    finally:
        if connection:
            cursor.close()
            connection.close()

    return render_template(
        "contest.html",
        id_concurs=id_concurs,
        standard_completed=standard_completed,
        reserve_completed=reserve_completed,
        quizzes=quizzes,
        contest_start_time=contest_start_time,
        current_time=current_time,
    )


@app.route("/final_report/<int:id_concurs>", methods=["GET"])
@authenticate
@authorize(['admin', 'hr'])
def final_report(id_concurs):
    if "username" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None
    logged_user = session["username"]

    try:
        connection = connect_db()
        cursor = connection.cursor()

        print(f"Generating final report for contest: {id_concurs}")

        # Fetch contest title
        cursor.execute(
            "SELECT titlu FROM concurs WHERE id_concurs = %s::VARCHAR", 
            (str(id_concurs),)
        )
        contest_title = cursor.fetchone()[0]  # Extrage titlul concursului

        # Fetch all participants and their scores
        cursor.execute(
            """
            SELECT 
                cc.username AS participant_username,
                cc.nume_prenume,
                chin.id_intrebare,
                si.scor AS punctaj_obtinut,
                SUM(si.scor) OVER (PARTITION BY cc.username, c.id_concurs, ch.tip) AS total_score,
                ch.tip
            FROM concurs c
            JOIN chestionare ch ON ch.id_concurs = c.id_concurs
            JOIN chestionar_intrebari chin ON chin.id_chestionar = ch.id_chestionar
            JOIN participanti_concurs pc ON c.id_concurs = pc.id_concurs
            JOIN concurenti cc ON cc.username = pc.username
            JOIN (
                SELECT 
                    username,
                    id_concurs,
                    id_intrebare,
                    SUM(punctaj) AS scor
                FROM participanti_raspuns
                GROUP BY username, id_concurs, id_intrebare
            ) AS si ON si.username = pc.username AND si.id_concurs = c.id_concurs AND si.id_intrebare = chin.id_intrebare
            WHERE c.id_concurs = %s::VARCHAR
            ORDER BY ch.tip, total_score DESC, cc.nume_prenume, chin.id_intrebare
            """,
            (str(id_concurs),)
        )

        rows = cursor.fetchall()
        print("Fetched rows:", rows)

        standard_participants = {}
        reserve_participants = {}

        # Organize the data into standard and reserve participants
        for row in rows:
            participant_username, nume_prenume, id_intrebare, punctaj_obtinut, total_score, tip = row
            participant_dict = standard_participants if tip == 'standard' else reserve_participants

            if participant_username not in participant_dict:
                participant_dict[participant_username] = {
                    "nume_prenume": nume_prenume,
                    "scores": {},
                    "total_score": total_score
                }

            participant_dict[participant_username]["scores"][id_intrebare] = punctaj_obtinut

        # Fetch question IDs for standard and reserve questions
        cursor.execute(
            """
            SELECT DISTINCT ci.id_intrebare
            FROM chestionar_intrebari ci
            JOIN chestionare ch ON ci.id_chestionar = ch.id_chestionar
            WHERE ch.id_concurs = %s::VARCHAR AND ch.tip = 'standard'
            ORDER BY ci.id_intrebare
            """,
            (str(id_concurs),)
        )
        standard_question_ids = [row[0] for row in cursor.fetchall()]

        cursor.execute(
            """
            SELECT DISTINCT ci.id_intrebare
            FROM chestionar_intrebari ci
            JOIN chestionare ch ON ci.id_chestionar = ch.id_chestionar
            WHERE ch.id_concurs = %s::VARCHAR AND ch.tip = 'rezerva'
            ORDER BY ci.id_intrebare
            """,
            (str(id_concurs),)
        )
        reserve_question_ids = [row[0] for row in cursor.fetchall()]

        return render_template(
            "final_report.html",
            username=logged_user,
            standard_participants=standard_participants,
            reserve_participants=reserve_participants,
            standard_question_ids=standard_question_ids,
            reserve_question_ids=reserve_question_ids,
            contest_title=contest_title  # Trimitem titlul concursului
        )

    except Exception as e:
        print("Error generating final report:", e)
        flash("A intervenit o eroare la generarea raportului final.", "danger")
        return redirect(url_for("view_contest", id_concurs=id_concurs))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()



@app.route(
    "/test_report/<int:id_concurs>/<int:id_set>/<username>/<int:total_score>",
    methods=["GET", "POST"],
)
@authenticate
@authorize(['admin', 'hr', 'concurent'])
def test_report(id_concurs, id_set, username, total_score):
    user_type = session["user_type"]
    if "username" not in session:
        return redirect(url_for("login"))

    connection = None
    cursor = None

    try:
        # Conectare la baza de date
        connection = connect_db()
        cursor = connection.cursor()

        # Obține titlul concursului
        contest_title = "Titlu necunoscut"
        cursor.execute(
            "SELECT titlu FROM concurs WHERE id_concurs = %s::VARCHAR", (str(id_concurs),)
        )
        contest_title_row = cursor.fetchone()
        if contest_title_row:
            contest_title = contest_title_row[0]

        if request.method == "POST":
            # Salvare raport PDF
            pdf_content = request.files.get("pdf_file")
            if not pdf_content:
                flash("Fișierul PDF nu a fost încărcat!", "danger")
                return redirect(url_for("view_contest", id_concurs=id_concurs))

            cursor.execute(
                """
                UPDATE participanti_scoruri
                SET raport_pdf = %s
                WHERE id_concurs = %s::VARCHAR AND username = %s
                """,
                (psycopg2.Binary(pdf_content.read()), str(id_concurs), username),
            )
            connection.commit()

            return jsonify({
                "status": "PDF saved successfully",
                "redirect_url": url_for("view_contest", id_concurs=id_concurs),
            })

        # Dacă este un request GET, generăm raportul testului
        cursor.execute(
            """
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
            """,
            (username, str(id_concurs), id_set),
        )

        rows = cursor.fetchall()
        questions = {}

        for row in rows:
            question_id, question_text, answer_id, answer_text, score, user_answer_id = row
            if question_id not in questions:
                questions[question_id] = {
                    "question_text": question_text,
                    "answers": [],
                    "user_answered_correctly": True,
                    "total_score": 0,
                }

            is_correct = user_answer_id is not None and score > 0
            selected = user_answer_id == answer_id

            if selected:
                if not is_correct:
                    questions[question_id]["user_answered_correctly"] = False
                else:
                    questions[question_id]["total_score"] += score

            questions[question_id]["answers"].append({
                "answer_id": answer_id,
                "answer_text": answer_text,
                "score": score,
                "is_correct": is_correct,
                "selected": selected,
            })

        for question in questions.keys():
            if any(answer["selected"] and not answer["is_correct"] for answer in questions[question]["answers"]):
                questions[question]["total_score"] = 0

        return render_template(
            "test_report.html",
            questions=questions,
            total_score=total_score,
            username=username,
            id_concurs=id_concurs,
            contest_title=contest_title,
            user_type=user_type
        )

    except (Exception, psycopg2.Error) as error:
        print("Eroare:", error)
        flash(f"A intervenit o eroare: {error}", "danger")
        return redirect(url_for("view_contest", id_concurs=id_concurs))

    finally:
        if cursor:
            cursor.close()
        if connection:
            connection.close()


            



@app.route("/view_users", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr'])
def view_users():
    username = session["username"]
    user_type = session["user_type"]
    users = []
    search_query = request.args.get("query", "").lower()
    column = request.args.get("column", "username")
    order = request.args.get("order", "asc")

    column_mapping = {
        "id": "u.id",
        "username": "u.username",
        "user_type": "u.user_type",
    }

    if column not in column_mapping:
        column = "username"

    try:
        connection = connect_db()
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
        users_data.append({"id": user[0], "username": user[1], "user_type": user[2]})

    # Sorting logic
    reverse_order = order == "desc"
    users_data.sort(key=lambda x: str(x[column]), reverse=reverse_order)

    has_users = len(users_data) > 0

    return render_template(
        "view_users.html",
        username=username,
        user_type=user_type,
        users=users_data,
        has_users=has_users,
        column=column,
        order=order,
    )


@app.route("/edit_user/<int:id>", methods=["GET", "POST"])
@authenticate
@authorize(['admin', 'hr'])
def edit_user(id):
    username = session.get("username")
    if request.method == "POST":
        new_username = request.form.get("username")
        password = request.form.get("password")
        user_type = request.form.get("user_type")

        if not new_username:
            flash("Username-ul este obligatoriu!", "danger")
            return redirect(url_for("edit_user", id=id))

        try:
            connection = connect_db()
            cursor = connection.cursor()

            cursor.execute(
                "SELECT username FROM users WHERE username = %s AND id != %s",
                (new_username, id),
            )
            if cursor.fetchone():
                flash("Username-ul există deja! Te rog să alegi altul.", "danger")
                return redirect(url_for("edit_user", id=id))

            if password:
                hashed_password = bcrypt.hashpw(
                    password.encode("utf-8"), bcrypt.gensalt()
                )
                cursor.execute(
                    """
                    UPDATE users
                    SET username = %s, password = %s, user_type = %s
                    WHERE id = %s
                """,
                    (new_username, hashed_password.decode("utf-8"), user_type, id),
                )
            else:
                cursor.execute(
                    """
                    UPDATE users
                    SET username = %s, user_type = %s
                    WHERE id = %s
                """,
                    (new_username, user_type, id),
                )

            connection.commit()
            flash("Utilizatorul a fost actualizat cu succes!", "success")
            return redirect(url_for("view_users"))

        except (Exception, psycopg2.Error) as error:
            print("Eroare la actualizare:", error)
            connection.rollback()
            flash(f"A apărut o eroare la actualizare: {error}", "danger")
            return redirect(url_for("edit_user", id=id))
        finally:
            if connection:
                cursor.close()
                connection.close()
    else:
        try:
            connection = connect_db()
            cursor = connection.cursor()

            cursor.execute(
                "SELECT id, username, user_type FROM users WHERE id = %s", (id,)
            )
            user = cursor.fetchone()

            if user:
                return render_template("edit_user.html", user=user, username=username)
            else:
                flash("Utilizatorul nu a fost găsit.", "danger")
                return redirect(url_for("view_users"))

        except (Exception, psycopg2.Error) as error:
            print("Eroare de bază de date:", error)
            flash(f"Eroare de bază de date: {error}", "danger")
            return redirect(url_for("view_users"))
        finally:
            if connection:
                cursor.close()
                connection.close()


@app.route("/delete_user/<int:id>")
@authenticate
@authorize('admin')
def delete_user(id):
    try:
        connection = connect_db()
        cursor = connection.cursor()

        connection.autocommit = False

        cursor.execute("SELECT username FROM users WHERE id = %s", (id,))
        username = cursor.fetchone()

        if username:
            username = username[0]

            cursor.execute(
                "DELETE FROM participanti_concurs WHERE username = %s", (username,)
            )
            cursor.execute(
                "DELETE FROM participanti_raspuns WHERE username = %s", (username,)
            )
            cursor.execute(
                "DELETE FROM participanti_scoruri WHERE username = %s", (username,)
            )

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

    return redirect(url_for("view_users"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
