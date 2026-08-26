# -*- coding: utf-8 -*-

import json
from pathlib import Path

from playwright.sync_api import expect, sync_playwright


def get_policies(page, p):
    page.goto('https://uslugi.tatarstan.ru/mis/tatarstan/init')
    page.wait_for_url("**/source**")
    
    policies = page.locator('#select_polis option')

    result = {}
    
    for i in range(policies.count()):
        option = policies.nth(i)
        value = option.get_attribute("value")
        if value:
            result[value] = option.text_content()
            
    policy_path = p / 'policy.json'   
    with policy_path.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=4)
    
    

def setup():
    pth = Path(".data")
    pth.mkdir(parents=True, exist_ok=True)

    phone_number = input('Введите номер телефона: +7').strip()
    password = input('Введите пароль: ').strip()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--disable-blink-features=AutomationControlled'],
            channel="chrome"
        )
        context = browser.new_context()
        page = context.new_page()
        page.goto('https://uslugi.tatarstan.ru', wait_until='domcontentloaded')
        
        page.get_by_role("button", name="Вход").click()
        
        phone = page.get_by_role("textbox", name="Телефон")
        psw = page.get_by_role("textbox", name="Пароль")
        phone.fill(phone_number)
        psw.fill(password)
        
        expect(phone).to_have_value(phone_number)
        expect(psw).to_have_value(password)
        
        page.get_by_role("button", name="Войти").click()
        page.wait_for_load_state("domcontentloaded")
        
        user_state = page.context.storage_state()
        (pth / 'user.json').write_text(
            json.dumps(user_state, ensure_ascii=False, indent=4),
            encoding='utf-8'
        )
        
        get_policies(page, pth)
        

        
if __name__ == '__main__':
    setup()