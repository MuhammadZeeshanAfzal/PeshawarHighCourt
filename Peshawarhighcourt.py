import os
import re
import time
import json
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from check import reformat_case_no


def shorten_case_no(case_no):
    """
    Shorten and reformat the case number.
    """
    return re.sub(r'[<>:"/\\|?*]', '', case_no)


def check_internet(url='http://www.google.com', timeout=5, interval=10):
    """
    Check for internet connection by reaching the given URL.
    Retries until a connection is established.
    """
    while True:
        try:
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                print("Internet is connected.")
                break
        except requests.ConnectionError:
            print(f"Internet disconnected. Retrying in {interval} seconds...")
            time.sleep(interval)


def load_existing_data(json_file):
    """
    Load existing data from the JSON file, if it exists.
    """
    if os.path.exists(json_file):
        try:
            with open(json_file, "r", encoding="utf-8") as file:
                return json.load(file)
        except json.JSONDecodeError:
            print(f"Error reading {json_file}. It might be corrupted.")
    return []


def is_file_already_downloaded(file_path):
    """
    Check if a file already exists in the given path.
    """
    return os.path.exists(file_path)


def download_file(url, file_path, retries=3, delay=5, backoff_factor=2):
    """
    Downloads a file from the specified URL and saves it to the given file path.
    """
    for attempt in range(retries):
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, stream=True, timeout=10)
            if response.status_code == 200:
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                print(f"File downloaded successfully: {file_path}")
                return True
                
            else:
                print(f"Failed to download file, status code: {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"Error downloading file: {e}, attempt {attempt + 1} of {retries}")
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= backoff_factor  # Exponential backoff
    time.sleep(3)
    print(f"Failed to download file after {retries} attempts.")
    return False


def scrape_case_data(driver, download_directory, output_file):
    """
    Scrape case data from the loaded web page and download associated files.
    Appends case details to the specified JSON file after each loop iteration.
    """
    existing_data = load_existing_data(output_file)
    existing_case_numbers = {case["Case No"] for case in existing_data}

    try:
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, '//*[@id="employee_list"]/tbody/tr'))
        )
        print("Case table loaded successfully.")

        while True:
            rows = driver.find_elements(By.XPATH, '//*[@id="employee_list"]/tbody/tr')
            print(f"Found {len(rows)} cases to scrape.")

            for i in range(1, len(rows) + 1):
                try:
                    case_no = driver.find_element(By.XPATH, f'//*[@id="employee_list"]/tbody/tr[{i}]/td[2]').text
                    remarks = driver.find_element(By.XPATH, f'//*[@id="employee_list"]/tbody/tr[{i}]/td[3]').text
                    author_judge = driver.find_element(By.XPATH, f'//*[@id="employee_list"]/tbody/tr[{i}]/td[4]').text
                    judgment_date = driver.find_element(By.XPATH, f'//*[@id="employee_list"]/tbody/tr[{i}]/td[5]').text
                    category = driver.find_element(By.XPATH, f'//*[@id="employee_list"]/tbody/tr[{i}]/td[7]').text
                    download_link = driver.find_element(By.XPATH, f'//*[@id="employee_list"]/tbody/tr[{i}]/td[8]/a')
                    download_url = download_link.get_attribute("href")

                    short_name = reformat_case_no(case_no)
                    filename = f"{short_name}.pdf"
                    file_path = os.path.join(download_directory, filename)

                    # Check if case is already in JSON or file already exists
                    if short_name in existing_case_numbers:
                        print(f"Skipping case {short_name}, already exists in JSON.")
                        continue
                    if is_file_already_downloaded(file_path):
                        print(f"Skipping download for {filename}, file already exists.")
                        continue

                    # Download the file
                    if download_file(download_url, file_path):
                        # Add case details to JSON
                        case_details = {
                            "Case No": short_name,
                            "Case Title": case_no,
                            "Remarks": remarks,
                            "Citation": author_judge,
                            "Judgment Date": judgment_date,
                            "Category": category,
                            "File Name": filename
                        }
                        existing_data.append(case_details)

                        # Save JSON after every successful addition
                        with open(output_file, "w", encoding="utf-8") as f:
                            json.dump(existing_data, f, indent=4)
                        print(f"Case {short_name} added to JSON.")

                except Exception as e:
                    print(f"Error scraping case at index {i}: {e}")

            # Check for next page
            try:
                next_button = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, '//*[@id="employee_list_next"]/a'))
                )
                next_button.click()
                time.sleep(3)  # Wait for next page to load
            except Exception as e:
                print("No more pages or pagination failed.")
                break

    except Exception as e:
        print(f"Error loading case table: {e}")


def main():
    """
    Main function to execute the scraping process.
    """
    check_internet()

    # Set download directory
    download_directory = "D:/pythonprogram/Pak_Law_scrapper/PDFfiles"
    os.makedirs(download_directory, exist_ok=True)

    # Set output JSON file
    output_file = "PeshawarHighCourt.json"

    # Set up WebDriver options
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_experimental_option("prefs", {
        "download.default_directory": download_directory,
        "download.prompt_for_download": False,
        "safebrowsing.enabled": True
    })

    # Launch browser and navigate to the URL
    driver = webdriver.Chrome(options=chrome_options)
    try:
        login_url = 'https://www.peshawarhighcourt.gov.pk/PHCCMS/reportedJudgments.php?action=search'
        driver.get(login_url)
        print("Website loaded successfully.")

        # Call the scraping function
        scrape_case_data(driver, download_directory, output_file)

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        driver.quit()
        print("Browser closed.")


if __name__ == "__main__":
    main()
