"""Contact dialog and invitation page shared by independent browser sessions."""
from pathlib import Path
import streamlit.components.v1 as components
import sqlite3
import uuid
from datetime import datetime, timezone
from urllib.parse import urlencode, urlsplit, urlunsplit

import streamlit as st
from services import contact_store as store


ERRORS = (ValueError, sqlite3.Error, OSError)


def report_error(error):
    if isinstance(error, ValueError):
        st.error(str(error))
    else:
        st.error('Байланыс серверіне қосылу мүмкін болмады. Қайта көріңіз.')


def base_url(value):
    parsed = urlsplit(value)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc or parsed.username:
        return ''
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))


def room_link(base, key, token):
    return base + '?' + urlencode({key: token})


def dismiss_contact():
    st.session_state.pop('contact_open', None)


def contact_room(state):
    if not state.get('contact_room'):
        state['contact_room'] = store.create_room()
    state['contact_destination'] = state['nav_B']
    return state['contact_room']


def open_contact(state, event):
    if not state.get('nav_B'):
        return
    contact_room(state)
    state['contact_base_url'] = base_url(event.get('page_url', ''))
    state['contact_open'] = 'call' if event.get('mode') == 'call' else 'chat'


def clear_contact(state):
    room = state.get('contact_room')
    if room:
        try:
            store.close_room(room['dispatcher'])
        except ValueError:
            pass  # Already expired or closed.
    state.pop('contact_room', None)
    state.pop('contact_open', None)


_phone_input = components.declare_component(
    'qadam_phone_input', path=str(Path(__file__).resolve().parents[1] / 'frontend' / 'phone_input'))


def display_phone(phone):
    if len(phone) == 12 and phone.startswith('+7'):
        return f'+7 {phone[2:5]} {phone[5:8]} {phone[8:]}'
    return phone


def phone_form(token, phone, submit_label='Нөмірді сақтау'):
    key = 'contact_phone_' + token[:10]
    event = _phone_input(saved=phone, label=submit_label, key=key, default=None)
    if isinstance(event, dict) and event.get('id') and event['id'] != st.session_state.get(key + '_ack'):
        st.session_state[key + '_ack'] = event['id']
        try:
            phone = store.save_phone(token, event.get('phone', ''))
            st.success('Телефон нөмірі сақталды.')
        except ERRORS as error:
            report_error(error)
    return phone


def submit_message(token, key):
    text = st.session_state.get(key)
    if not text:
        return
    pending_key = 'contact_pending_' + token[:10]
    pending = st.session_state.get(pending_key)
    if not pending or pending['body'] != text:
        pending = {'body': text, 'id': uuid.uuid4().hex}
        st.session_state[pending_key] = pending
    try:
        store.send_message(token, pending['body'], pending['id'])
    except ERRORS:
        return  # The composer displays the unsent text for retry.
    st.session_state.pop(pending_key, None)


@st.fragment(run_every='2s')
def message_history(token):
    try:
        data = store.snapshot(token)
    except ERRORS as error:
        report_error(error)
        return
    st.caption('Хабарламалар 2 секунд сайын жаңарады · Соңғы 200 хабарлама')
    with st.container(height=260, border=True):
        if not data['messages']:
            st.caption('Әңгімелесуді бірінші хабарламадан бастаңыз.')
        for message in data['messages']:
            mine = message['role'] == data['role']
            with st.chat_message('user' if mine else 'assistant'):
                name = 'Диспетчер' if message['role'] == 'dispatcher' else 'Шақыртушы'
                stamp = datetime.fromtimestamp(message['sent'], timezone.utc).strftime('%H:%M UTC')
                st.caption(name + ' · ' + stamp)
                st.text(message['body'])


def chat_panel(token):
    message_history(token)
    key = 'message_' + token[:10]
    with st.container():
        st.chat_input('Хабарлама жазыңыз…', max_chars=2000, key=key,
                      on_submit=submit_message, args=(token, key))
    pending = st.session_state.get('contact_pending_' + token[:10])
    if pending:
        st.warning('Хабарлама жіберілмеді. Қайта жіберу үшін мәтінді төменнен көшіріңіз.')
        st.code(pending['body'], language=None)


@st.dialog('Шақыртушымен байланыс', width='small', on_dismiss=dismiss_contact)
def contact_dialog():
    state = st.session_state
    room = state.get('contact_room')
    if not room:
        return
    token = room['dispatcher']
    try:
        data = store.snapshot(token)
    except ERRORS as error:
        report_error(error)
        if st.button('Жаңа байланыс ашу'):
            state['contact_room'] = store.create_room()
            st.rerun()
        return
    if state['contact_open'] == 'call':
        st.subheader('Қоңырау шалу')
        phone = phone_form(token, data['phone'], 'Қоңырау шалу')
        if phone:
            st.link_button('☎ ' + display_phone(phone), 'tel:' + phone, use_container_width=True)
            st.caption('Құрылғының қоңырау қолданбасы ашылады. Компьютерде қоңырау қолданбасы қажет.')
    else:
        invitation(room, token, state.get('contact_base_url', ''))
        chat_panel(token)


def caller_page(token):
    st.title('Qadam · Байланыс')
    try:
        data = store.snapshot(token)
    except ERRORS as error:
        report_error(error)
        return
    st.caption('Диспетчермен чат' if data['role'] == 'caller' else 'Шақыртушымен чат')
    with st.expander('Телефон нөмірі', expanded=not data['phone']):
        phone = phone_form(token, data['phone'])
        if phone and data['role'] == 'dispatcher':
            st.link_button('☎ ' + display_phone(phone), 'tel:' + phone, use_container_width=True)
    chat_panel(token)


def invitation(room, token, page_url):
    with st.expander('Шақыртушыны чатқа шақыру'):
        base = st.text_input('Жобаның қолжетімді мекенжайы',
                             value=page_url,
                             placeholder='http://192.168.1.10:8501')
        base = base_url(base)
        if base:
            st.text_input('Шақыртушыға жіберілетін сілтеме',
                          value=room_link(base, 'chat', room['caller']))
            st.caption('Осы сілтемені шақыртушыға жіберіңіз. Ол 24 сағат жарамды.')
            st.text_input('Диспетчердің жеке сілтемесі',
                          value=room_link(base, 'dispatch_chat', token))
            st.caption('Жеке сілтемені өзіңізге сақтаңыз. Онымен чатқа қайта кіре аласыз.')
        st.caption('Басқа құрылғы жобаның серверіне қосыла алуы керек. Бір Wi-Fi ішінде компьютердің желілік мекенжайын қолданыңыз.')

@st.fragment(run_every='2s')
def quick_phone(token):
    try:
        phone = store.phone_number(token)
    except ERRORS as error:
        report_error(error)
        return
    phone = phone_form(token, phone, 'Қоңырау шалу')
    if phone:
        st.link_button('☎ ' + display_phone(phone), 'tel:' + phone, use_container_width=True)


def quick_page(token, mode):
    try:
        data = store.snapshot(token)
    except ERRORS as error:
        report_error(error)
        return
    if data['role'] != 'dispatcher':
        st.error('Диспетчердің жеке сілтемесі қажет.')
        return
    st.markdown('<style>.block-container{padding:1rem!important}header,footer{display:none!important}</style>', unsafe_allow_html=True)
    if mode == 'call':
        quick_phone(token)
    else:
        invitation({'caller': st.query_params.get('invite', '')}, token,
                   base_url(st.context.url))
        chat_panel(token)
