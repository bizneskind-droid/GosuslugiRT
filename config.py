import json
import sys
import traceback
from copy import deepcopy
from functools import cache
from pathlib import Path
from typing import TypedDict, cast

import httpx

all_directions = {
    '1': ['Терапевт, Педиатр', 'terapevt'], 
    '2': ['Стоматология', 'stomatolog'],
    '3': ['Гинекология', 'ginekolog'],
    '4': ['Другие специальности', 'other_doctor']
}

client: httpx.Client

class GlobalsParams(TypedDict):
    globalsid: str

class PolicyParams(TypedDict):
    globalsid: str
    policy_key: str | None


class DoctorParams(TypedDict):
    globalsid: str
    filter: str | None
    attachment: int


class AvailableDates(TypedDict):
    full_date: str
    date: str
    week: str


class Doctor(TypedDict):
    id: str
    name: str
    comment: str
    snils: None
    room_id: str
    group: None
    clinic: dict[str, str]
    service: dict[str, str]
    available_dates: list[AvailableDates]


class State(TypedDict):
    policy_params: PolicyParams
    doctor_params: DoctorParams
    directions: dict[str, list[str]]
    name: str
    doctors: list[Doctor]
    selected_doctors: list[str]
    time: str | None
    
def get_cookies() -> dict[str, str]:
    p = Path(".data/user.json")
    cookies = json.loads(p.read_text())['cookies']

    result = {}
    for cookie in cookies:
        name = cookie['name']
        value = cookie['value']
        result[name] = value

    return result


def init_session(directions: dict[str, list]) -> State:
    if client is None:
        raise RuntimeError('HTTP-клиент не инициализирован')

    response = client.get('/init')
    globals_id = response.url.params["globalsid"]
    
    state: State = {
        "policy_params": {
            "globalsid": globals_id,
            "policy_key": None,
        },
        "doctor_params": {
            "globalsid": globals_id,
            "filter": None,
            "attachment": 1,
        },
        "directions": directions,
        "name": "",
        "doctors": [],
        "selected_doctors": [],
        "time": None,
    }
    
    return state
    
    
def choose_policy(state: State):
    p = Path('.data/policy.json')
    policy = json.loads(p.read_text())

    for key in policy:
        num = int(key) + 1
        print(f'{num} - {policy[key]}')
    print()
    
    user_choice = int(input('Выберите полис: ').strip()) 
    policy_key = str(user_choice - 1)
    state['name'] = policy[policy_key]
    state['policy_params']['policy_key'] = policy_key
    
    policy_params = tuple(state['policy_params'].items())
    set_policy(policy_params)


@cache
def set_policy(policy_params: tuple):
    params = dict(policy_params)
    
    client.get(
    '/check-policy-ajax',
    params=params
    )
    
    
def choose_direction(state: State):
    directions = state['directions']
    for i in directions:
        print(f'{i} - {directions[i][0]}')
    print()
    
    user_choice = input('Выберите специальность: ').strip()
    direction = directions[user_choice][1]
    if direction == 'stomatolog':
        state['doctor_params']['attachment'] = 0
    state['doctor_params']['filter'] = direction
    
    doctor_params = tuple(state['doctor_params'].items())
    policy_key = state['policy_params']['policy_key']
    state['doctors'] = get_doctors(doctor_params, policy_key)
    

@cache
def get_doctors(doctor_params: tuple, policy_key: int) -> list[Doctor]:
    doctor_params_dict = dict(doctor_params)
        
    response = client.get(
    '/ajax-source',
    params=doctor_params_dict
    )
    
    return cast(list[Doctor], response.json()['resources'])


def choose_doctors(state: State):
    doctors = [doctor['name'] for doctor in state['doctors'] \
               if not doctor['available_dates']]
    
    if not doctors:
        raise ValueError("Нет врачей")
        
    doctors_dict = {}
    for i, doctor in enumerate(doctors, start=1):
        doctors_dict[str(i)] = doctor
        print(f'{i} - {doctor}')
        print('-' * 100)

    user_choice = input('Выберите одного или нескольких врачей через пробел: ').strip()
    state['selected_doctors'] = []
    for key in user_choice.split():
        doctor_name = doctors_dict[key]
        state['selected_doctors'].append(doctor_name)
        
        
def choose_time(state: State):
    user_choice = input("Хотите добавить автозапуск? (Да/Нет): ").lower()
    if user_choice == 'да':
        selected_time = input("Введите время (например 7:00): ").strip()
        state['time'] = selected_time
        set_task(selected_time)
    else:
        state['time'] = None
    
def set_task(selected_time):
    platform = sys.platform
    
    if platform == "win32":
        from autostart_windows import windows_task
        windows_task(selected_time)
    elif platform == "linux":
        pass
        
        
def add_appointment(appointments: dict,
                    state: State
    ) -> dict[str, dict]:
    
    time = state['time']
    name = state['name']
    policy_params = state['policy_params']
    doctor_params = state['doctor_params']
    direction = state['doctor_params']['filter']
    doctors = state['selected_doctors']

    entry = appointments.setdefault(time, {}).setdefault(name, {})
    
    entry['policy_params'] = policy_params
  
    entry.setdefault('directions', {}) \
         .setdefault(direction, {})['doctor_params'] = doctor_params
    
    entry['directions'][direction]['doctors'] = doctors
    

    return deepcopy(appointments)


def finish_record(appointments: dict,
                  state: State,
                  current: int
    ) -> tuple[dict[str, dict], int]:
    
    appointments = add_appointment(appointments, state)
    current = choose_next_act(current, 'Завершить', 'Добавить запись')
    
    start = 0
    finish = 5
    if current == finish:
        p = Path('.data/appointments.json')
        with p.open('w', encoding='utf-8') as f:
            json.dump(appointments, f, ensure_ascii=False, indent=4)
    else:
        current = start

    return appointments, current
    
    
def choose_next_act(
        current: int,
        first: str='Дальше',
        second: str='Назад'
    ) -> int: 
    
    attempts = 3    
    for _ in range(attempts):
        try:       
            print(f'''
                1 - {first}
                2 - {second}
                ''')
            
            act = int(input('Введите чиcло: ').strip())
            print()
            
            if act == 1:
                return current + 1
            elif act == 2 and current != 0:
                return current - 1
            elif act == 2:
                return current
            else:
                raise ValueError('Выберите один из доступных вариантов')
            
        except ValueError as e:
            print(f'Ошибка: {e}')
            
    raise ValueError("Превышены попытки")
    
def runner(directions):
    state = init_session(directions)
    appointments = {}
    
    steps = [
        choose_policy,
        choose_direction,
        choose_doctors,
        choose_time,
    ]
    
    current = 0
    while True:
        steps[current](state)
        
        current = choose_next_act(current)
        
        if current == len(steps):
            appointments, current = finish_record(appointments, state, current)
            if current > 0:
                break
                

def set_config():
    global client
    try:
        client = httpx.Client(
            follow_redirects=True,
            base_url='https://uslugi.tatarstan.ru/mis/tatarstan',
            cookies=get_cookies()
        ) 
        
        runner(all_directions)  
        
    except ValueError:
        print("Ошибка: Такого варианта нет") 
    
    except httpx.HTTPError as e:
        print(f'Сетевая ошибка: {e}')
        
    except Exception:  # noqa: BLE001
        traceback.print_exc()
        
    finally:
        if client is not None:
            client.close()


if __name__ == '__main__':
    set_config()
