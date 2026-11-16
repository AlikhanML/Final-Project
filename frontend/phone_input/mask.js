'use strict';
const field = document.querySelector('input');
const button = document.querySelector('button');
const form = document.querySelector('form');
let previousSaved;
let dirty = false;
const digits = text => text.replace(/[^0-9]/g, '');
const format = number => [number.slice(0,3), number.slice(3,6), number.slice(6,10)].filter(Boolean).join(' ');

function draw(number, caret) {
  field.value = format(number);
  let index = 0, count = 0;
  while (index < field.value.length && count < caret) {
    if (field.value[index++] !== ' ') count++;
  }
  field.setSelectionRange(index, index);
  button.disabled = number.length !== 10;
}

function edit(text, deletion) {
  const number = digits(field.value);
  let start = digits(field.value.slice(0, field.selectionStart)).length;
  let end = digits(field.value.slice(0, field.selectionEnd)).length;
  if (deletion && start === end) {
    if (deletion === 'back') start = Math.max(0, start - 1);
    if (deletion === 'forward') end = Math.min(number.length, end + 1);
  }
  if (!deletion && !text) return;
  const inserted = text.slice(0, 10 - (number.length - end + start));
  dirty = true;
  draw(number.slice(0, start) + inserted + number.slice(end), start + inserted.length);
}

function pasted(text) {
  const number = digits(text);
  if (/^\s*\+/.test(text) && !/^\s*\+7/.test(text)) return '';
  if (number.length === 11 && /^[78]/.test(number)) return number.slice(1);
  return number.length <= 10 ? number : '';
}

field.addEventListener('paste', event => {
  event.preventDefault();
  edit(pasted(event.clipboardData.getData('text')), null);
});
field.addEventListener('beforeinput', event => {
  if (!event.cancelable) return;
  if (event.inputType === 'insertText') {
    event.preventDefault();
    edit(digits(event.data || ''), null);
  } else if (['deleteContentBackward','deleteContentForward'].includes(event.inputType)) {
    event.preventDefault();
    edit('', event.inputType === 'deleteContentBackward' ? 'back' : 'forward');
  }
});
field.addEventListener('input', () => {
  const caret = digits(field.value.slice(0, field.selectionStart)).length;
  dirty = true;
  draw(pasted(field.value) || digits(field.value).slice(0,10), caret);
});

function post(type, data = {}) {
  window.parent.postMessage({isStreamlitMessage:true, type, ...data}, '*');
}
form.onsubmit = event => {
  event.preventDefault();
  const number = digits(field.value);
  if (number.length !== 10) return;
  dirty = false;
  post('streamlit:setComponentValue', {value:{phone:'+7'+number, id:Date.now()+'-'+Math.random()},dataType:'json'});
};
window.addEventListener('message', event => {
  if (event.source !== window.parent || event.data?.type !== 'streamlit:render') return;
  const {args, theme} = event.data;
  button.textContent = args.label;
  if (theme) {
    document.body.style.setProperty('--text', theme.textColor);
    document.body.style.setProperty('--surface', theme.secondaryBackgroundColor);
  }
  if (args.saved !== previousSaved && !dirty) {
    const national = /^\+7[0-9]{10}$/.test(args.saved) ? args.saved.slice(2) : '';
    draw(national, national.length);
  }
  previousSaved = args.saved;
  post('streamlit:setFrameHeight', {height:form.offsetHeight+2});
});
post('streamlit:componentReady', {apiVersion:1});
