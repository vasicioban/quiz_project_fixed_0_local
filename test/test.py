from selenium import webdriver
from selenium.webdriver.common.by import By
import time as t
from datetime import datetime
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC



import psycopg2

#fct pt reinitializare id

def reset_sequence(cursor):
    try:
        # Verifica daca secventa ajunge la 500
        cursor.execute("SELECT last_value FROM id_intrarisen")
        last_value = cursor.fetchone()[0]
        if last_value >= 500:
            # Reinitializare id la 1
            cursor.execute("SELECT setval('id_intrarisen', 1, FALSE)")
            print("Secventa a fost reinitializata.")
    except Exception as e:
        print(f"Eroare la reinitializarea secventei: {e}")


#fct pt inserare date in baza de date
def insert_sql_pstgr(v_data_sen, v_data_txt, v_ape, v_gaze, v_nucl, v_carb, v_foto, v_eolian, v_bmasa, v_ispoz, v_sold, v_prod, v_cons, data_scriere):
    # PostgreSQL
    connection = psycopg2.connect(host='localhost',
                                  port=5432,
                                  user='postgres',
                                  password='1234',
                                  database='vasi')


    with connection:
        with connection.cursor() as cursor:
            try:
                 # Update tabel
                cursor.execute("SELECT nextval('id_intrarisen')") #id_intrarisen - secventa
                id_urmator = int(cursor.fetchall()[0][0])
                print("Id următor:", id_urmator)  
                sql = ('UPDATE intrarisen SET id_intrarisen = %s, data_sen = %s, data_txt = %s, hidro = %s, hidrocarb = %s, nuclear = %s, carb = %s, fotov = %s,'
                       ' eolian = %s, biomasa = %s, istocare = %s, sold = %s, prod = %s, cons = %s, data_write = %s')
                cursor.execute(sql, (id_urmator, v_data_sen, v_data_txt, v_ape, v_gaze, v_nucl, v_carb, v_foto, v_eolian, v_bmasa, v_ispoz, v_sold, v_prod, v_cons, data_scriere))
                connection.commit()
                print("Datele au fost inserate cu succes în baza de date.")
                # Apelare fct pt reinitializarea secventei
                reset_sequence(cursor)
            except Exception as e:
                # In caz de orice exceptie, afiseaza un mesaj de eroare
                print(f"Eroare la inserarea datelor în PostgreSQL: {e}")
 

#fct pt citire date de pe site
def read_data():
    while True:
        try:
            cService = webdriver.ChromeService(executable_path='C:/work/quiz_project - restart-new/test/chromedriver.exe')
            driver = webdriver.Chrome(service = cService)
            driver.minimize_window()
            driver.get('https://www.transelectrica.ro/web/tel/sen-harta')
             
            wait = WebDriverWait(driver, 10)  # Wait for up to 10 seconds
            
            v_cons = wait.until(EC.presence_of_element_located((By.ID, "SEN_Harta_CONS_value"))).text
            v_prod = wait.until(EC.presence_of_element_located((By.ID, "SEN_Harta_PROD_value"))).text
            v_sold = wait.until(EC.presence_of_element_located((By.ID, "SEN_Harta_SOLD_value"))).text
            v_carb = wait.until(EC.presence_of_element_located((By.ID, "SEN_Harta_CARB_value"))).text
            v_gaze = wait.until(EC.presence_of_element_located((By.ID, "SEN_Harta_GAZE_value"))).text
            v_hidro = wait.until(EC.presence_of_element_located((By.ID, "SEN_Harta_APE_value"))).text
            v_nucl = wait.until(EC.presence_of_element_located((By.ID, "SEN_Harta_NUCL_value"))).text
            v_eolian = wait.until(EC.presence_of_element_located((By.ID, "SEN_Harta_EOLIAN_value"))).text
            v_foto = wait.until(EC.presence_of_element_located((By.ID, "SEN_Harta_FOTO_value"))).text
            v_bmasa = wait.until(EC.presence_of_element_located((By.ID, "SEN_Harta_BMASA_value"))).text
            v_ispoz = wait.until(EC.presence_of_element_located((By.ID, "SEN_Harta_ISPOZ_value"))).text
            v_data_sen_txt = wait.until(EC.presence_of_element_located((By.ID, "SEN_date"))).text.replace(" ora "," ")
            
            v_data_sen = datetime.strptime(v_data_sen_txt, "%d-%m-%Y %H:%M:%S")
            data_ora_curenta = datetime.now()
            data_ora_txt = data_ora_curenta.strftime("%d-%m-%Y %H:%M:%S")
            data_scriere = datetime.strptime(data_ora_txt, "%d-%m-%Y %H:%M:%S")

            print("Data de scriere:", data_scriere)
            print("Datele inserate:", v_data_sen, v_data_sen_txt, v_hidro, v_gaze, v_nucl, v_carb, v_foto, v_eolian, v_bmasa, v_ispoz, v_sold, v_prod, v_cons, data_scriere)
            insert_sql_pstgr(v_data_sen, v_data_sen_txt, v_hidro, v_gaze, v_nucl, v_carb, v_foto, v_eolian, v_bmasa, v_ispoz, v_sold, v_prod, v_cons, data_scriere)
            print("Datele au fost procesate si inserate in baza de date.")

        except Exception as e:
            print(f"Eroare la citire si inserare: {e}")
            data = str(datetime.now())
            with open("erori.txt", "a") as f:
                f.write(data + " - Eroare" + '\n')
                f.close()
        t.sleep(30)

#Apelare fct pt citire date
read_data()

 