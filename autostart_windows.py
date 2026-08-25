from datetime import date, datetime, time, timedelta
from pathlib import Path

import win32com.client

triggers = {
    'task_trigger_time': 1,
    'task_trigger_daily': 2,
    'task_trigger_weekly': 3
}

actions = {
    'task_action_execute': 0,
    'task_action_com_handler': 5,
    'task_action_send_email': 6,
    'task_action_show_message': 7
}

task_logon_types = {
    "task_logon_none": 0,                           # логон-тип не задан / не используется
    "task_logon_password": 1,                       # логин+пароль, пароль хранится в системе, работает без сессии и без логона
    "task_logon_s4u": 2,                            # без пароля, без сессии, только локальные права (без доступа к сети от имени юзера)
    "task_logon_interactive_token": 3,              # требует активную сессию пользователя, пароль не нужен, полный токен с сетевыми правами
    "task_logon_group": 4,                          # запуск от имени группы безопасности
    "task_logon_service_account": 5,                # системные учётки (LocalSystem/LocalService/NetworkService), без пароля, без сессии
    "task_logon_interactive_token_or_password": 6,  # сначала пробует интерактивный токен, если нет сессии — fallback на пароль
}

creation_tasks = {
    'task_validate_only': 1,
    'task_create': 2,
    'task_update': 4,
    'task_create_or_update': 6
}


def set_triggers(hour, minute, definition):
    target_time = time(hour, minute)
    now = datetime.now().time()
    today = date.today()
    if now > target_time:
        tomorrow = today + timedelta(days=1)
        scheduled_time = datetime.combine(tomorrow, target_time)
    else:
        scheduled_time = datetime.combine(today, target_time)

    run_at = scheduled_time.strftime("%Y-%m-%dT%H:%M:%S")

    trigger = definition.Triggers.Create(triggers['task_trigger_time'])
    trigger.StartBoundary = run_at
    trigger.EndBoundary = run_at


def set_actions(selected_time, definition):
    working_dir = Path.cwd()
    python_exe = working_dir / ".venv" / "Scripts" / "python.exe"
    script = working_dir / "main.py" 

    action = definition.Actions.Create(actions['task_action_execute'])
    action.Path = str(python_exe)
    action.Arguments = f'{str(script)} --time {selected_time}'
    action.WorkingDirectory = str(working_dir)

    # Разбудить компьютер
    definition.Settings.WakeToRun = True

    # Удалить задачу после expiration
    expiration = 'PT5M'
    definition.Settings.DeleteExpiredTaskAfter = expiration


def register_task(root, hour, minute, definition):
    user_id = None
    password = None
    
    root.RegisterTaskDefinition(
        f"Gosuslugi_{hour}-{minute}",
        definition, 
        creation_tasks['task_create_or_update'],
        user_id,
        password,
        task_logon_types["task_logon_interactive_token"]
    )

def windows_task(selected_time):
    scheduler = win32com.client.Dispatch("Schedule.Service")
    scheduler.Connect()

    root = scheduler.GetFolder("\\")

    definition = scheduler.NewTask(0)
    
    hour, minute = map(int, selected_time.split(':'))
    set_triggers(hour, minute, definition)
    set_actions(selected_time, definition)
    register_task(root, hour, minute, definition)
    
    
