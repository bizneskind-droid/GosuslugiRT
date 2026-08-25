import argparse
import asyncio
import json
import traceback
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from random import choice, uniform
from typing import Any, Literal, cast

import httpx

from config import DoctorParams, GlobalsParams, PolicyParams, get_cookies

headers = {
    'x-requested-with': 'XMLHttpRequest',
}

    
async def send_request(
        client: httpx.AsyncClient,
        method: Literal["GET", "POST"],
        url: str,
        params: PolicyParams | DoctorParams | GlobalsParams| None = None,
        data: Mapping[str, dict[str, Any] | str] | None = None,
        json: Any | None = None,
    ) -> httpx.Response:
    
    attempts = 3

    try:
        for _ in range(attempts):
            response = await client.request(
                method=method,
                url=url,
                params=cast(Any, params),
                data=data,
                json=json,
            )
            response.raise_for_status()
            return response
        
    except httpx.HTTPStatusError as e:
        print(f'{url}: {e}')
        print('Ожидание 3 секунды')
        await asyncio.sleep(3)

    except httpx.TimeoutException:
        print(f'{url}: Превышено время ожидания')

    except httpx.HTTPError as e:
        print(f'{url}: Сетевая ошибка: {e}')

    raise RuntimeError(f'Не удалось выполнить запрос: {url}')
        
def create_data_init() -> dict[str, dict[str, Any]]:
    return {'select_doctor': {
        'user': None,
        'doctor': None
    }}

def create_globals_params() -> GlobalsParams:
    return {'globalsid': ''}

@dataclass
class GosuslugiRT:

    whois: str
    client: httpx.AsyncClient
    policy_params: PolicyParams
    doctor_params: DoctorParams
    doctors: list[str]
    globals_params: GlobalsParams = field(default_factory=create_globals_params)
    data_init: dict[str, dict[str, Any]] = field(default_factory=create_data_init)

    async def get_globals_id(self):
        response = await send_request(
            self.client,
            'GET',
            '/init',
        )
        print(self.whois + ':', response.url)
        globals_id = response.url.params["globalsid"]

        self.globals_params['globalsid'] = globals_id
        self.doctor_params['globalsid'] = globals_id
        self.policy_params['globalsid'] = globals_id


    async def get_user(self):
        response = await send_request(
            self.client,
            'GET',
            '/check-policy-ajax',
            self.policy_params
        )

        print(self.whois + ':', response.url)
        
        self.data_init['select_doctor']['user'] = response.json()['user']


    async def check_dates(self):
        
        attempts = 5
        
        for _ in range(attempts):
            response = await send_request(
                self.client,
                'GET',
                '/ajax-source',
                self.doctor_params
            )

            print(self.whois + ':', response.url)
            doctors = response.json()['resources']

            for selected_doctor in self.doctors:
                for doctor in doctors:
                    if doctor['name'] == selected_doctor and doctor['available_dates']:
                        data_init_selected_doctor: dict[str, Any] = deepcopy(
                            self.data_init
                        )
                        data_init_selected_doctor['select_doctor']['doctor'] = doctor
                        data_init_selected_doctor['select_doctor'] = json.dumps(
                            data_init_selected_doctor['select_doctor']
                        )

                        await self.init_data(data_init_selected_doctor, selected_doctor)

            await asyncio.sleep(uniform(1, 1.5))

            if not self.doctors:
                break    


    async def init_data(self, data_init: dict[str, Any], doctor: str):

        response = await send_request(
            self.client,
            "POST",
            '/init-data-form-source',
            self.globals_params,
            data_init
        )

        print(self.whois + ':', response.url)

        await self.choose_ticket(doctor)

    async def choose_ticket(self, doctor: str):
        response = await send_request(
            self.client,
            'GET',
            '/ajax-calendar-data',
            self.globals_params
        )

        print(self.whois + ':', response.url)

        ticket = choice(response.json()['tickets'])
        appointment_time = choice(ticket)

        day = appointment_time['date']['day']
        month = appointment_time['date']['month']
        year = appointment_time['date']['year']
        select_time, select_id = appointment_time['time'], appointment_time['id']
        self.date_time = f'{day}.{month}.{year} {select_time}'
        select_data = {
            'selectedDate': self.date_time,
            'selectedId': select_id
        }

        await self.confirm_record(select_data, doctor)


    async def confirm_record(self, select_data: dict[str, str], doctor: str):

        response = await send_request(
            self.client,
            'POST',
            '/init-record',
            self.globals_params,
            select_data
        )
        print(self.whois + ':', response.url)
        
        if response.json()['status'] == 'success':
            self.doctors.remove(doctor)
            print(f'{self.whois} - {doctor} - запись на {self.date_time}')


    async def runner(self):
        try:
            await self.get_globals_id()
            await self.get_user()
            await self.check_dates()

        except Exception:
            print(f'{self.whois}: {traceback.print_exc()}')

async def book_appointment(client: httpx.AsyncClient, appointments: dict[str, dict]):

    coroutines  = list()
    for name, name_data in appointments.items():
        policy_params = name_data['policy_params']

        for direction, direction_data in name_data['directions'].items():
            doctor_params = direction_data['doctor_params']
            doctors = direction_data['doctors']

            whois = f'{name} - {direction}'
            patient = GosuslugiRT(whois, client, policy_params, doctor_params, doctors)
            coroutines.append(asyncio.create_task(patient.runner()))

    await asyncio.wait(coroutines)


async def main(selected_time):

    async with httpx.AsyncClient(
        follow_redirects=True,
        base_url='https://uslugi.tatarstan.ru/mis/tatarstan',
        cookies=get_cookies(),
        headers=headers
    ) as client:
        
        p = Path('.data/appointments.json')
        all_appointments = json.loads(p.read_text())
        
        appointments = {}
        for appointment_time in all_appointments:
            if appointment_time == selected_time:
                appointments.update(all_appointments[selected_time])

        await book_appointment(client, appointments)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--time", default=None)
        
    args = parser.parse_args()
    
    asyncio.run(main(args.time))


