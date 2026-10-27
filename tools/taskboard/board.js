"use strict";

const POLL_MS = 2000;

const rowsBody = document.getElementById("rows");
const boardTable = document.getElementById("board");
const emptyLine = document.getElementById("empty");
const banner = document.getElementById("banner");
const storePath = document.getElementById("store-path");
const refreshAge = document.getElementById("refresh-age");
const counters = {
	open: document.getElementById("summary-open"),
	overdue: document.getElementById("summary-overdue"),
	today: document.getElementById("summary-today"),
	this_week: document.getElementById("summary-this-week"),
	later: document.getElementById("summary-later"),
	undated: document.getElementById("summary-undated")
};

let payload = null;
let refreshedAt = 0;
let editor = null;
let pollTimer = null;

function apply(next) {
	payload = next;
	refreshedAt = Date.now();
	for (const key of Object.keys(counters)) {
		counters[key].textContent = next.summary[key];
	}
	storePath.textContent = next.store.path;
	renderRows(next.tasks);
	showAge();
}

function renderRows(tasks) {
	if (editor !== null) {
		return;
	}
	rowsBody.replaceChildren();
	for (const task of tasks) {
		rowsBody.appendChild(buildRow(task));
	}
	boardTable.hidden = tasks.length === 0;
	emptyLine.hidden = tasks.length !== 0;
}

function buildRow(task) {
	const row = document.createElement("tr");
	row.appendChild(cell("#" + task.id, "id"));
	row.appendChild(dueCell(task));
	row.appendChild(cell(task.category, "category"));
	row.appendChild(cell(task.title, "title"));
	row.appendChild(cell(task.tags.join(", "), "tags"));
	return row;
}

function cell(text, kind) {
	const node = document.createElement("td");
	node.className = kind;
	node.textContent = text;
	return node;
}

function dueCell(task) {
	const node = document.createElement("td");
	node.className = "due";
	const label = document.createElement("span");
	label.className = "due-label";
	label.tabIndex = 0;
	label.textContent = task.due_label;
	label.addEventListener("click", () => openEditor(task, node));
	label.addEventListener("keydown", (event) => {
		if (event.key === "Enter") {
			event.preventDefault();
			openEditor(task, node);
		}
	});
	const message = document.createElement("span");
	message.className = "message";
	node.appendChild(label);
	node.appendChild(message);
	return node;
}

function openEditor(task, node) {
	cancelEditor();
	const input = document.createElement("input");
	input.type = "text";
	input.className = "due-input";
	input.value = task.due_date || "";
	input.addEventListener("keydown", (event) => {
		if (event.key === "Enter") {
			event.preventDefault();
			submitEdit(task.id, input.value);
		} else if (event.key === "Escape") {
			event.preventDefault();
			cancelEditor();
		}
	});
	node.replaceChild(input, node.firstElementChild);
	node.classList.add("editing");
	editor = {task: task, input: input, message: node.lastElementChild};
	input.focus();
	input.select();
}

function cancelEditor() {
	if (editor === null) {
		return;
	}
	editor = null;
	if (payload !== null) {
		renderRows(payload.tasks);
	}
}

async function submitEdit(taskId, value) {
	const current = taskById(taskId);
	if (current === null) {
		return;
	}
	let response;
	try {
		response = await fetch("/api/due", {
			method: "POST",
			headers: {"Content-Type": "application/json"},
			body: JSON.stringify({id: taskId, value: value, expected_chg_ts: current.chg_ts})
		});
	} catch (error) {
		showMessage("connection lost — retrying");
		return;
	}
	let reply = {};
	try {
		reply = await response.json();
	} catch (error) {
		reply = {};
	}
	if (response.ok) {
		editor = null;
		apply(reply);
		return;
	}
	showMessage(describe(reply));
	if (response.status === 409 && reply.task) {
		adopt(reply.task);
	}
}

function describe(reply) {
	if (reply.error === "conflict" && reply.task) {
		return "conflict: someone else changed this row, now due " + (reply.task.due_date || "none") + " — press Enter to retry";
	}
	return reply.message || "the edit was rejected";
}

function showMessage(text) {
	editor.message.textContent = text;
}

function adopt(task) {
	for (const current of payload.tasks) {
		if (current.id === task.id) {
			current.chg_ts = task.chg_ts;
			current.due_date = task.due_date;
			current.due_label = task.due_label;
		}
	}
}

function taskById(taskId) {
	if (payload === null) {
		return null;
	}
	return payload.tasks.find((task) => task.id === taskId) || null;
}

async function poll() {
	try {
		const response = await fetch("/api/tasks");
		if (!response.ok) {
			throw new Error("HTTP " + response.status);
		}
		banner.hidden = true;
		apply(await response.json());
	} catch (error) {
		banner.hidden = false;
	}
}

function schedule() {
	window.clearTimeout(pollTimer);
	if (document.hidden) {
		return;
	}
	pollTimer = window.setTimeout(tick, POLL_MS);
}

async function tick() {
	await poll();
	schedule();
}

function showAge() {
	if (refreshedAt === 0) {
		return;
	}
	const seconds = Math.round((Date.now() - refreshedAt) / 1000);
	refreshAge.textContent = "refreshed " + seconds + "s ago";
}

document.addEventListener("visibilitychange", () => {
	window.clearTimeout(pollTimer);
	if (document.hidden) {
		return;
	}
	tick();
});

tick();
window.setInterval(showAge, 1000);
