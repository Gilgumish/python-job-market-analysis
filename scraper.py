import csv
import os
import time
import asyncio
from aiohttp import ClientSession
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

VACANCIES_URL = "https://jobs.dou.ua/vacancies/?category=Python"


def click_all_load_more_buttons(driver: webdriver.Chrome) -> None:
    page_number = 1
    while True:
        try:
            load_more_button = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".more-btn a"))
            )
            if "display: none" in load_more_button.get_attribute("style"):
                break

            load_more_button.click()

            page_number += 1
        except Exception:
            break


async def fetch_detailed_description(session: ClientSession, job_url: str) -> dict:
    async with session.get(job_url) as response:
        job_page = await response.text()
        soup = BeautifulSoup(job_page, "html.parser")
        job_description_div = soup.find("div", class_="b-typo vacancy-section")
        if job_description_div:
            job_description = job_description_div.text.strip()
            job_description = job_description.replace("\xa0", " ")
        else:
            job_description = "No description available"

        city_span = soup.find("span", class_="place bi bi-geo-alt-fill")
        if city_span:
            city = city_span.text.strip()
        else:
            city = "Unknown"

        return {"description": job_description, "city": city}


async def fetch_all_descriptions(job_listings: list) -> list:
    async with ClientSession() as session:
        tasks = []
        for job in job_listings:
            task = asyncio.ensure_future(
                fetch_detailed_description(session, job["url"])
            )
            tasks.append(task)
        descriptions = await asyncio.gather(*tasks)
        for i, job in enumerate(job_listings):
            job["description"] = descriptions[i]["description"]
            job["city"] = descriptions[i]["city"]
        return job_listings


def parse_page(driver: webdriver.Chrome) -> list:
    soup = BeautifulSoup(driver.page_source, "html.parser")
    vacancy_cards = soup.find_all("li", class_="l-vacancy")
    job_listings = []
    for vacancy in vacancy_cards:
        title_tag = vacancy.find("a", class_="vt")
        if title_tag:
            title = title_tag.text.strip()
            url = title_tag["href"]
            job_listings.append(
                {"title": title, "url": url, "description": "", "city": ""}
            )
    return job_listings


def write_to_csv(vacancies: list, filename: str) -> None:
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["title", "url", "description", "city"])
        for vacancy in vacancies:
            writer.writerow(
                [
                    vacancy["title"],
                    vacancy["url"],
                    vacancy["description"],
                    vacancy["city"],
                ]
            )


async def get_all_vacancies() -> None:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), options=chrome_options
    )
    driver.get(VACANCIES_URL)

    click_all_load_more_buttons(driver)

    job_listings = parse_page(driver)
    detailed_job_listings = await fetch_all_descriptions(job_listings)

    write_to_csv(detailed_job_listings, "data/vacancies.csv")
    driver.quit()


if __name__ == "__main__":
    asyncio.run(get_all_vacancies())
