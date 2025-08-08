"""
해당 파일을 실행하기 위한 패키지 설치 명령어
pip install gspread oauth2client selenium webdriver-manager
"""

import os
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import cafe_param as pa
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains

# --- 로그인 함수 (driver, wait 반환) ---
def login_cafe(username, password, login_url, headless=False):
    try:
        # 1.드라이버 & WebDriverWait 설정
        options = webdriver.ChromeOptions()
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')

        if headless:
            options.add_argument('--headless')

        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=options
        )
        wait = WebDriverWait(driver, 10)

        # 2.카페 페이지 열기 + 로그인 버튼 클릭
        print(f"아이디: {username} 로그인 시도중")
        driver.get(login_url)
        wait.until(EC.element_to_be_clickable((By.ID, "gnb_login_button"))).click()

        # 3.로그인 레이어 뜨기 대기
        wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.login_form")))

        # 4.ID/PW input 요소 찾기
        id_field = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "div#input_item_id > input.input_id")
        ))
        pw_field = wait.until(EC.visibility_of_element_located(
            (By.CSS_SELECTOR, "div#input_item_pw > input.input_pw")
        ))

        # 5.화면 중앙 스크롤 & 포커스
        for elem in (id_field, pw_field):
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
            time.sleep(0.2)
            elem.click()
            time.sleep(0.2)

        # 6.JS로 value 주입 & input 이벤트 발생
        def js_set_value(elem, text):
            driver.execute_script("arguments[0].value = '';", elem)
            driver.execute_script("""
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            """, elem, text)
            time.sleep(1)

        js_set_value(id_field, username)
        js_set_value(pw_field, password)

        # 7.로그인 버튼 클릭
        submit_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button.btn_login")))
        submit_btn.click()

        # 8.로그인 완료 대기
        print(f"아이디: {username} 로그인 완료")
        time.sleep(2)
        return driver, wait
    
    except Exception as e:
        print(f"[ERROR] 로그인 실패: {e}")
        driver.quit()
        return None, None


# --- 포스팅 함수 (게시판 선택 로직 포함) ---
def posting_cafe(username, password, cafe_name, board_name, TITLE, PARAGRAPHS, img_dir, headless=False):
    login_url = pa.CAFE_URL.get(cafe_name)
    write_url = pa.WRITING_URL.get(cafe_name, login_url)

    driver, wait = login_cafe(username, password, login_url, headless)
    if not driver:
        return
    try:
        print(f"[2] 글쓰기 페이지 이동: {write_url}")
        driver.get(write_url)
        time.sleep(2)

        # 게시판 선택
        print(f"[2] 게시판 선택: {board_name}")
        sel_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'div.FormSelectButton > button')))
        sel_btn.click()
        time.sleep(0.5)
        option = wait.until(EC.element_to_be_clickable((
            By.XPATH,
            f"//div[contains(@class,'select_option')]//li[normalize-space()='{board_name}']"
        )))
        option.click()
        time.sleep(1)

        # 제목 입력
        title_el = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'textarea.textarea_input')))
        title_el.click(); title_el.clear(); title_el.send_keys(TITLE)
        time.sleep(0.5)

        # 본문 캔버스 클릭
        canvas = wait.until(EC.visibility_of_element_located((
            By.CSS_SELECTOR,
            'div.se-container div.se-content section.se-canvas'
        )))
        ActionChains(driver).move_to_element_with_offset(canvas, 10, 10).click().perform()
        time.sleep(0.2)

        # 내용 입력
        for idx, para in enumerate(PARAGRAPHS, start=1):
            img_path = None
            for ext in ('jpg','png'):
                path = os.path.join(img_dir, f"{idx}.{ext}")
                if os.path.isfile(path): img_path = path; break
            if img_path:
                print(f"[2] {idx}번 이미지 업로드: {img_path}")
                img_btn = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[data-log='dot.img']")))
                img_btn.click(); time.sleep(0.3)
                inp = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type=file]')))
                inp.send_keys(img_path); time.sleep(0.3)
                before = len(driver.find_elements(By.CSS_SELECTOR, 'img.se-image-resource'))
                WebDriverWait(driver,15).until(lambda d: len(d.find_elements(By.CSS_SELECTOR,'img.se-image-resource'))>before)
                time.sleep(0.3)
            print(f"[2] {idx}번 텍스트 입력")
            ActionChains(driver).send_keys(para).send_keys(Keys.ENTER).perform()
            time.sleep(0.5)

        time.sleep(5)
        # 등록
        submit = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='등록']/..")))
        submit.click(); print('[3] 글 등록 완료'); time.sleep(3)

    except Exception as e:
        print(f"[ERROR] 포스팅 중 예외 발생: {e}")
    finally:
        driver.quit()


# --- Google Sheet 연결 ---
def connect_to_sheet():
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        pa.JSON_PATH,
        [
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/drive'
        ]
    )
    client = gspread.authorize(creds)
    return client.open_by_key(pa.SPREADSHEET_ID).worksheet(pa.WORKSHEET_NAME)


# --- GUI 클래스 ---
class CafePosterGUI:
    def __init__(self, master):
        self.master = master; master.title('Naver Cafe 자동 글쓰기 GUI')
        # 카페 선택
        ttk.Label(master, text='카페:').grid(row=0,column=0,sticky='e')
        self.cafe_cb = ttk.Combobox(master, values=list(pa.CAFE_URL.keys()), state='readonly')
        self.cafe_cb.grid(row=0,column=1,pady=5)
        # 게시판 선택
        ttk.Label(master, text='게시판:').grid(row=1,column=0,sticky='e')
        self.board_cb = ttk.Combobox(master, state='readonly')
        self.board_cb.grid(row=1,column=1,pady=5)
        self.cafe_cb.bind('<<ComboboxSelected>>', self.update_boards)
        # 계정 선택
        ttk.Label(master, text='계정:').grid(row=2,column=0,sticky='e')
        self.acc_cb = ttk.Combobox(master, values=list(pa.CAFE_INFO.keys()), state='readonly')
        self.acc_cb.grid(row=2,column=1,pady=5)
        # 글 목록 로드
        ttk.Button(master, text='글 목록 로드', command=self.load_articles).grid(row=3,column=0,columnspan=2,pady=5)
        # 글 제목 선택
        ttk.Label(master,text='글 제목:').grid(row=4,column=0,sticky='e')
        self.article_cb = ttk.Combobox(master,state='readonly',width=50)
        self.article_cb.grid(row=4,column=1,pady=5)
        # 게시 시작
        ttk.Button(master,text='게시 시작',command=self.start_posting).grid(row=5,column=0,columnspan=2,pady=5)
        # 상태창
        self.status = scrolledtext.ScrolledText(master,width=80,height=20)
        self.status.grid(row=6,column=0,columnspan=2,pady=5)
        self.status.configure(state='disabled')
        self.sheet=None; self.titles=[]

    def update_boards(self, event):
        cafe = self.cafe_cb.get()
        boards = pa.BOARD_LIST.get(cafe, [])
        self.board_cb['values'] = boards
        if boards: self.board_cb.current(0)

    def status_callback(self,msg):
        self.status.configure(state='normal'); self.status.insert(tk.END,msg); self.status.see(tk.END); self.status.configure(state='disabled')


    def load_articles(self):
        try:
            self.sheet=connect_to_sheet(); self.titles=self.sheet.col_values(1)[1:]; self.article_cb['values']=self.titles
            if self.titles: self.article_cb.current(0)
            messagebox.showinfo('완료','글 목록을 불러왔습니다.')
        except Exception as e:
            messagebox.showerror('오류',f'글 목록 로드 실패:\n{e}')

        
    def start_posting(self):
        cafe=self.cafe_cb.get(); board=self.board_cb.get(); account=self.acc_cb.get(); title=self.article_cb.get()
        if not all([cafe,board,account,title]): messagebox.showwarning('경고','모두 선택해주세요.'); return
        idx=self.titles.index(title)+2
        try: row=self.sheet.get(f'A{idx}:F{idx}')[0]
        except Exception as e: messagebox.showerror('오류',f'데이터 가져오기 실패:\n{e}'); return
        TITLE, p1,p2,p3,p4,url_text = row; PARAGRAPHS=[p1,p2,p3,p4,url_text]
        parent=os.path.dirname(pa.IMAGE_FOLDER1); folder=f'picture{idx-1}'; img_dir=os.path.join(parent,folder)
        if not os.path.isdir(img_dir): img_dir=pa.IMAGE_FOLDER1
        threading.Thread(target=posting_cafe,args=(account, pa.CAFE_INFO[account], cafe, board, TITLE, PARAGRAPHS, img_dir, False)).start()
        self.status_callback(f"[GUI] '{TITLE}' 게시 시작 (카페:{cafe}, 게시판:{board})\n")


if __name__=='__main__':
    root=tk.Tk(); app=CafePosterGUI(root); root.mainloop()


