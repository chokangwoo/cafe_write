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
import cafe_param2 as pa
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
        try:
            driver.quit()
        except:
            pass
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


# --- (신규) 시트 B~J를 사용한 배치 포스팅 함수 ---
def run_batch_from_sheet(row_start=2, row_end=None, headless=False):
    """
    시트의 B~J 컬럼을 읽어 자동 포스팅.
    B=계정, C=카페, D=게시판, E=제목, F~J=본문(총 5개 단락)
    row_start: 시작 행(헤더 제외 기본 2)
    row_end:   끝 행(미지정 시, B열 데이터가 있는 마지막 행까지)
    """
    sheet = connect_to_sheet()

    # B열(계정) 기준으로 데이터 존재 구간 파악
    colB = sheet.col_values(2)  # 1-based index, 2는 B열
    total_rows = len(colB)
    if row_end is None:
        row_end = total_rows

    print(f"[BATCH] 대상 행: {row_start} ~ {row_end}")

    for r in range(row_start, row_end + 1):
        try:
            # B~J = 9칸
            values = sheet.get(f'B{r}:J{r}')
            if not values or not values[0]:
                print(f"[SKIP] {r}행: 값 없음")
                continue

            row = values[0]
            # 필요한 만큼 패딩 (셀 비어있어도 인덱스 에러 방지)
            while len(row) < 9:
                row.append("")

            account, cafe, board, TITLE, p1, p2, p3, p4, p5 = row

            # 필수값 체크
            if not (account and cafe and board and TITLE):
                print(f"[SKIP] {r}행: 필수값 누락 (account={account}, cafe={cafe}, board={board}, title={TITLE})")
                continue

            if account not in pa.CAFE_INFO:
                print(f"[SKIP] {r}행: pa.CAFE_INFO에 계정 비등록 → {account}")
                continue
            if cafe not in pa.CAFE_URL:
                print(f"[SKIP] {r}행: pa.CAFE_URL에 카페 비등록 → {cafe}")
                continue

            # 본문 구성 (빈칸은 자동 스킵)
            PARAGRAPHS = [x for x in [p1, p2, p3, p4, p5] if str(x).strip() != ""]

            # 이미지 폴더 결정 (기존 로직 유지: picture{r-1} 폴더 우선)
            parent = os.path.dirname(pa.IMAGE_FOLDER1)
            folder = f'picture{r-1}'
            img_dir = os.path.join(parent, folder)
            if not os.path.isdir(img_dir):
                img_dir = pa.IMAGE_FOLDER1

            print(f"[BATCH] {r}행 게시 시작 → 계정:{account}, 카페:{cafe}, 게시판:{board}, 제목:{TITLE}")
            posting_cafe(
                username=account,
                password=pa.CAFE_INFO[account],
                cafe_name=cafe,
                board_name=board,
                TITLE=TITLE,
                PARAGRAPHS=PARAGRAPHS,
                img_dir=img_dir,
                headless=headless
            )
            print(f"[BATCH] {r}행 게시 완료")

        except Exception as e:
            print(f"[ERROR] {r}행 처리 중 예외: {e}")


if __name__=='__main__':
    run_batch_from_sheet(row_start=2, row_end=None, headless=False)



