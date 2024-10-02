import getpass
import os
import sys
import urllib3

import dotenv
import platformdirs
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

dirs = platformdirs.PlatformDirs("unina-res-scraper")
config_file_name = dirs.user_config_dir + os.sep + ".env"
download_dir = dirs.user_downloads_dir

config = {}

def save_credentials() -> None:
    mail = input("Mail studente (puoi anche omettere @studenti.unina.it)\n> ").strip()
    password = getpass.getpass("Password\n> ")
    if not mail.endswith("@studenti.unina.it"):
        mail += "@studenti.unina.it"
    with open(config_file_name, 'w') as f:
        print("Salvando")
        f.write(
            f"UNINA_MAIL={mail}\n"
            f"UNINA_PASS={password}"
        )
    print(f"Credenziali salvate nel file `{config_file_name}`!")

def login() -> tuple | None:
    config = dotenv.dotenv_values(config_file_name)
    try:
        credentials = {
            "username": config["UNINA_MAIL"],
            "password": config["UNINA_PASS"]
        }
    except KeyError:
        print("\n\n\nATTENZIONE:")
        print("Sembra essere la prima volta che usi questo programma.")
        print("Vuoi seguire la procedura guidata per collegare il tuo account?")
        choice = input("(S/n) > ").strip().lower()
        if choice == "" or choice[0] in ("y", "s"):
            save_credentials()
            return login()
        else:
            print("Procedura abortita.")
            return None
    try:
        print(f"Tentando il login (max 10s)")
        req = requests.post(LOGIN_URL, json=credentials, verify=False, timeout=10)
        utente = req.json()
        return (utente, req.cookies)
    except requests.exceptions.JSONDecodeError:
        print("Credenziali invalide. Controlla il file `.env` per"
              " eventuali errori")
        return None
    except requests.exceptions.ConnectTimeout:
        print("Docenti UniNA non è raggiungibile: il servizio è offline oppure"
              " non sei collegato alla rete.")
        return None

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
    path = f"{download_dir}{os.sep}{name.replace(' ', '_')}" \
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
        only_files: bool = False,
        numbered_elements: bool = False
        ) -> bool:
    path = dir.get("percorso")
    print(f"Percorso: {path}")
    letter = None
    if only_dirs or only_files:
        letter = "D" if only_dirs else "F"
    elements = get_elements(dir, letter)
    if len(elements) == 0:
        return False
    for index, element in enumerate(elements):
        prefix = f"{index}) " if numbered_elements else ""
        print(f"{prefix}{element.get('tipo', 'Corso')}"
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



class State:
    def __init__(self):
        self.state: callable = self.startup_state
        self.dir_tree = []

    def no_state(self):
        pass

    def change_state(self, new_state: callable):
        self.state = new_state
        #os.system(CLEAR_COMMAND)

    def startup_state(self):
        if not os.path.exists(config_file_name):
            print("\n\n\nATTENZIONE:")
            print("È la prima volta che usi questo programma.")
            print("Segui la procedura guidata per collegare il tuo account.")
            os.makedirs(dirs.user_config_dir, exist_ok=True)
            save_credentials()
        self.change_state(self.login_state)

    def login_state(self):
        self.access: tuple|None = login()

        if self.access == None:
            print("Accesso non riuscito :(")
            return 1

        self.change_state(self.teacher_search_state)

    def teacher_search_state(self):
        name = input("Inserire nome e cognome del docente da ricercare: ").strip()
        self.user, self.cookies = self.access
        self.professore_json = None
        self.professori_json = requests.get(SEARCH_URL, params={
            "nome": f"{name.lower()}",
            "p": 0,
            "s": 10
        }, verify=False).json()

        if "error" in self.professori_json:
            print(f"Errore: {self.professori_json['error']}")
            print("Docenti UniNA sta avendo problemi.")
            return

        self.professore_json = self.professori_json.get("content", [])

        if len(self.professori_json) == 0:
            print("Errore: il nome inserito non è valido!")
            return 2

        elif len(self.professori_json) >= 1:
            self.change_state(self.teacher_selection_state)

    def teacher_selection_state(self):
        if len(self.professori_json) > 1:
            print("Ho trovato questi professori:")
            for index, professore in enumerate(self.professori_json):
                print(f"{index}) {professore['nome']} {professore['cognome']}")
            while True:
                try:
                    choice = int(input("Quale scegli?\n> ").strip())
                    self.professore_json = self.professori_json[choice]
                    break
                except IndexError:
                    print("Non è una scelta valida.")
                except ValueError:
                    print("Non hai inserito un numero!")
        else:
            self.professore_json = self.professori_json[0]
        
        self.teacher_url = TEACHER_URL.replace("INSERT_ID", self.professore_json["id"])
        self.teacher_materials = requests.get(
                self.teacher_url, verify=False
                ).json()
        
        self.change_state(self.course_selection)
    
    def course_selection(self):
        print(f"I corsi di {self.professore_json.get('nome')} {self.professore_json.get('cognome')}:")
        list_dir(dict(percorso="/", contenutoCartella=self.teacher_materials), numbered_elements=True)
        while True:
            try:
                index = int(input("Di quale corso vuoi i materiali?\n> "))
                break
            except ValueError:
                print("Non hai inserito un numero!")
        course_url = self.teacher_url + f"/{self.teacher_materials[index]['id']}"
        self.dir_tree.append(requests.get(course_url, cookies=self.cookies, params={
            "codIns": self.teacher_materials[index].get('codInse')
        }, verify= False).json())
        if self.dir_tree[-1].get("code", 200) == 403:
            print("Impossibile accedere al corso "
                f"{self.teacher_materials[index]['nome']}\n"
                f"Errore: {self.dir_tree[-1].get('error', 'Errore sconosciuto.')}")
            return 3
        
        self.change_state(self.course_exploration)
    
    def course_exploration(self):
        if len(self.dir_tree) == 0:
            self.change_state(self.course_selection)
            return 0

        if not list_dir(self.dir_tree[-1]):
            print("La cartella è vuota.")
        while True:
            try:
                action = int(input("Cosa vuoi fare?\n"
                                "1) Entra in una cartella\n"
                                "2) Torna nella cartella precedente\n"
                                "3) Scarica un file\n"
                                "0) Esci\n\n"
                                "> "))
                break
            except ValueError:
                print("Non hai inserito un numero!")
        os.system(CLEAR_COMMAND)
        if action == 0:
            return 4
        if action == 1:
            if not list_dir(self.dir_tree[-1], only_dirs=True, numbered_elements=True):
                return
            while True:
                try:
                    dir_index = int(input("In quale cartella vuoi entrare?\n> "))
                    break
                except ValueError:
                    print("Non hai inserito un numero!")
            self.dir_tree.append(enter_dir(
                self.teacher_url, self.cookies, self.dir_tree[-1], dir_index
            ))
            os.system(CLEAR_COMMAND)
        elif action == 2:
            self.dir_tree.pop()
        elif action == 3:
            if not list_dir(self.dir_tree[-1], only_files=True, numbered_elements=True):
                print("Non ci sono file, tantomeno da scaricare.")
                return 5
            print("\n-1) Scarica tutti i file nella cartella\n"
                    "-2) Scarica tutti i file nella cartella"
                    " e nelle sottocartelle\n")
            while True:
                try:
                    file_index = int(input("Quale file vuoi scaricare?\n> "))
                    break
                except ValueError:
                    print("Non hai inserito un numero!")
            os.system(CLEAR_COMMAND)
            download_element(
                self.teacher_url,
                self.cookies,
                self.dir_tree[-1],
                file_index,
                f"{self.professore_json.get('nome')} {self.professore_json.get('cognome')}"
            )

def main():
    a = State()
    while True:
        return_code = a.state()
        if return_code == 4:
            break
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nProgramma chiuso.")
