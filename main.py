import getpass
import os
import sys
import urllib3

import dotenv
import requests
import requests.cookies

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

BASE_URL = "https://www.docenti.unina.it"
LOGIN_URL = f"{BASE_URL}/webdocenti-be/auth/login-post-evo"
SEARCH_URL = f"{BASE_URL}/webdocenti-be/docenti"
TEACHER_URL = f"{BASE_URL}/#!/professor/INSERT_ID/materiale_didattico"
TEACHER_URL = f"{BASE_URL}" \
    "/webdocenti-be/docenti/INSERT_ID/materiale-didattico/areapubb"
MATERIAL_URL = f"{BASE_URL}/webdocenti-be/allegati/materiale-didattico"

CLEAR_COMMAND = "cls" if os.name == "nt" else "clear"

del requests.cookies.RequestsCookieJar.set_cookie # Necessario perché altrimenti set cookie mi avrebbe formattato il cookie e non avrebbe funzionato

config = {}

def save_credentials() -> None:
    mail = input("Mail studenti unina\n> ").strip()
    password = getpass.getpass("Password\n> ")
    with open('.env', 'w') as f:
        f.write(
            f"UNINA_MAIL={mail}\n"
            f"UNINA_PASS={password}"
        )
    print("Credenziali salvate nel file `.env`!")

def login() -> tuple | None:
    config = dotenv.dotenv_values(".env")
    try:
        credentials = {
            "username": config["UNINA_MAIL"],
            "password": config["UNINA_PASS"]
        }
    except KeyError:
        print("\n\n\nATTENZIONE:")
        print("Non sono stati trovati email e password nel file `.env`.")
        print("Vuoi seguire la procedura guidata per collegare il tuo account?")
        choice = input("(S/n) > ").strip().lower()
        if choice == "" or choice[0] in ("y", "s"):
            save_credentials()
            return login()
        else:
            print("Procedura abortita.")
            return None
    req = requests.post(LOGIN_URL, json=credentials, verify=False)
    utente = req.json()
    return (utente, req.cookies) if "error" not in utente.keys() else None

def get_elements(dir: dict, letter: str | None = None) -> list:
    if letter != None:
        return list(
            filter(lambda x : x.get("tipo") == letter,
                   dir.get("contenutoCartella", []))
        )
    return dir.get("contenutoCartella", [])

def download_file(
        cookies, file_obj: dict,
        name: str = "unnamed_professor"
        ) -> None:
    new_url = MATERIAL_URL + f"/{file_obj.get('id')}"
    file = requests.get(
        new_url, cookies=cookies, verify=False, allow_redirects=True
    )
    path = f"{os.getcwd()}{os.sep}{name.replace(' ', '_')}" \
        f"{file_obj.get('percorso', '').replace('/', os.sep)}{os.sep}"
    os.makedirs(path, exist_ok=True)
    filename = file_obj.get('nome')
    full_path = f"{path}{filename}"
    with open(full_path, "wb") as f:
        f.write(file.content)
    print(f"File {full_path} salvato!")


def list_dir(
        dir: dict,
        only_dirs: bool = False,
        only_files: bool = False
        ) -> bool:
    path = dir.get("percorso")
    print(f"Percorso: {path}")
    letter = None
    if only_dirs or only_files:
        letter = "D" if only_dirs else "F"
    elements = get_elements(dir, letter)
    if len(elements) == 0:
        print(f"La cartella {path} è vuota")
        return False
    for index, element in enumerate(elements):
        print(f"{index}) {element.get('tipo', 'Corso')}"
              " - "
              f"{element['nome'].replace('_', ' ')}")
    print()
    return True

def download_element(teacher_url: str,
                     cookies, dir: dict,
                     index: int,
                     name: str = "unnamed_professor") -> None:
    files = get_elements(dir, "F")
    if index == -1:
        for file in files:
            download_file(cookies, file, name)
    elif index == -2:
        download_element(teacher_url, cookies, dir, -1, name)
        for subdir_index in range(len(get_elements(dir, "D"))):
            subdir = enter_dir(teacher_url, cookies, dir, subdir_index)
            download_element(teacher_url, cookies, subdir, -2, name)
    else:
        download_file(cookies, files[index], name)
    
def enter_dir(teacher_url : str, cookies, dir : dict, index : int) -> dict:
    dirs = get_elements(dir, "D")
    new_url = teacher_url + f"/{dirs[index].get('id')}"
    return requests.get(new_url, cookies=cookies, params={
            "codIns": dirs[index].get('codInse')
        }, verify= False).json()

def main() -> int:
    if not os.path.exists(".env"):
        print("\n\n\nATTENZIONE:")
        print("È la prima volta che usi questo programma.")
        print("Segui la procedura guidata per collegare il tuo account.")
    
        save_credentials()
    access = login()
    if access == None:
        print("Accesso non riuscito :(")
        return 2
    name = input("Inserire nome e cognome del docente da ricercare: ").strip()
    user, cookies = access
    try:
        professore_json = requests.get(SEARCH_URL, params={ 
            "nome": f"{name.lower()}",
            "p": 0, 
            "s": 10
        }, verify=False).json()["content"][0]
    except IndexError as e:
        print("Errore: il nome inserito non è valido!")
        return 1
    teacher_url = TEACHER_URL.replace("INSERT_ID", professore_json["id"])
    teacher_materials = requests.get(
            teacher_url, verify=False
            ).json()
    #print(teacher_materials)
    print(f"I corsi di {professore_json['nome']} {professore_json['cognome']}:")
    #for index, course in enumerate(teacher_materials):
    #    print(f"{index}) {course['nome'].replace('_', ' ')}")
    while True:
        list_dir(dict(percorso="/", contenutoCartella=teacher_materials))
        index = int(input("Di quale corso vuoi i materiali?\n> "))
        course_url = teacher_url + f"/{teacher_materials[index]['id']}"
        directory = requests.get(course_url, cookies=cookies, params={
            "codIns": teacher_materials[index].get('codInse')
        }, verify= False).json()
        #print(directory)
        #list_dir(directory)
        while True:
            action = int(input("Cosa vuoi fare?\n"
                           "1) Elenca gli elementi della cartella corrente\n"
                           "2) Entra in una cartella\n"
                           "3) Scarica un file\n"
                           "0) Esci\n\n"
                           "> "))
            os.system(CLEAR_COMMAND)
            if action == 0:
                sys.exit(0)
            if action == 1:
                list_dir(directory)
            elif action == 2:
                if not list_dir(directory, only_dirs=True):
                    continue
                dir_index = int(input("In quale cartella vuoi entrare?\n> "))
                directory = enter_dir(
                    teacher_url, cookies, directory, dir_index
                )
                os.system(CLEAR_COMMAND)
            elif action == 3:
                if not list_dir(directory, only_files=True):
                    print("Non ci sono file, ora mostrerò solo le cartelle...")
                    list_dir(directory) 
                print("\n-1) Scarica tutti i file nella cartella\n"
                      "-2) Scarica tutti i file nella cartella"
                      " e nelle sottocartelle\n")
                file_index = int(input("Quale file vuoi scaricare?\n> "))
                os.system(CLEAR_COMMAND)
                download_element(
                    teacher_url,
                    cookies,
                    directory,
                    file_index,
                    f"{professore_json['nome']} {professore_json['cognome']}"
                )
            
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nProgramma chiuso.")