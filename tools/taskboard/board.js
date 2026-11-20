"use strict";

const POLL_MS = 2000;
const UNCAT = "";

const board = document.getElementById("board");
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
let dragging = null;
let pollTimer = null;

function apply(next) {
	payload = next;
	refreshedAt = Date.now();
	for (const key of Object.keys(counters)) {
		counters[key].textContent = next.summary[key];
	}
	storePath.textContent = next.store.path;
	renderBoard(next.tasks);
	showAge();
}

function renderBoard(tasks) {
	if (editor !== null || dragging !== null) {
		return;
	}
	board.replaceChildren();
	if (tasks.length === 0) {
		board.hidden = true;
		emptyLine.hidden = false;
		return;
	}
	board.hidden = false;
	emptyLine.hidden = true;

	const cats = new Set(tasks.map((t) => t.category));
	const ordered = [UNCAT, ...[...cats].filter((c) => c !== UNCAT).sort()];
	for (const cat of ordered) {
		board.appendChild(buildColumn(cat, tasks.filter((t) => t.category === cat)));
	}
}

function columnTitle(cat) {
	return cat === UNCAT ? "Uncategorised" : cat;
}

function buildColumn(cat, tasks) {
	const col = document.createElement("div");
	col.className = "column";
	col.dataset.category = cat;
	col.addEventListener("dragover", (event) => {
		event.preventDefault();
		col.classList.add("drag-over");
	});
	col.addEventListener("dragleave", () => col.classList.remove("drag-over"));
	col.addEventListener("drop", (event) => {
		event.preventDefault();
		col.classList.remove("drag-over");
		const id = Number(event.dataTransfer.getData("text/plain"));
		if (!Number.isNaN(id)) {
			moveCategory(id, cat);
		}
	});
	const title = document.createElement("h2");
	title.className = "column-title";
	title.textContent = columnTitle(cat);
	col.appendChild(title);
	const cards = document.createElement("div");
	cards.className = "cards";
	const ordered = [...tasks].sort((a, b) => {
		const da = a.due_ts === null ? Infinity : a.due_ts;
		const db = b.due_ts === null ? Infinity : b.due_ts;
		if (da !== db) {
			return da - db;
		}
		return a.id - b.id;
	});
	for (const task of ordered) {
		cards.appendChild(buildCard(task));
	}
	col.appendChild(cards);
	return col;
}

function buildCard(task) {
	const card = document.createElement("div");
	card.className = "card";
	card.draggable = true;
	card.dataset.id = String(task.id);
	card.addEventListener("dragstart", (event) => {
		dragging = task.id;
		card.classList.add("dragging");
		event.dataTransfer.setData("text/plain", String(task.id));
		event.dataTransfer.effectAllowed = "move";
	});
	card.addEventListener("dragend", () => {
		dragging = null;
		card.classList.remove("dragging");
		document.querySelectorAll(".column").forEach((c) => c.classList.remove("drag-over"));
		if (payload !== null) {
			renderBoard(payload.tasks);
		}
	});

	const title = document.createElement("p");
	title.className = "card-title";
	title.textContent = task.title;
	card.appendChild(title);

	const meta = document.createElement("div");
	meta.className = "card-meta";
	const idSpan = document.createElement("span");
	idSpan.className = "card-id";
	idSpan.textContent = "#" + task.id;
	meta.appendChild(idSpan);

	const dueWrap = document.createElement("span");
	dueWrap.className = "due";
	const dueLabel = document.createElement("span");
	dueLabel.className = "due-label";
	dueLabel.tabIndex = 0;
	dueLabel.textContent = task.due_label;
	dueLabel.addEventListener("click", (event) => {
		event.stopPropagation();
		openEditor(task, dueWrap);
	});
	dueLabel.addEventListener("keydown", (event) => {
		if (event.key === "Enter") {
			event.preventDefault();
			openEditor(task, dueWrap);
		}
	});
	const msg = document.createElement("span");
	msg.className = "message";
	dueWrap.appendChild(dueLabel);
	dueWrap.appendChild(msg);
	meta.appendChild(dueWrap);
	card.appendChild(meta);

	if (task.tags && task.tags.length) {
		const tags = document.createElement("p");
		tags.className = "card-tags";
		tags.textContent = task.tags.join(", ");
		card.appendChild(tags);
	}
	return card;
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
		renderBoard(payload.tasks);
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
		banner.hidden = false;
		banner.textContent = "connection lost — retrying";
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
	if (editor !== null) {
		editor.message.textContent = text;
	}
}

function adopt(task) {
	if (payload === null) {
		return;
	}
	for (const current of payload.tasks) {
		if (current.id === task.id) {
			current.chg_ts = task.chg_ts;
			current.due_date = task.due_date;
			current.due_label = task.due_label;
			current.category = task.category;
		}
	}
}

async function moveCategory(taskId, newCategory) {
	const current = taskById(taskId);
	if (current === null || current.category === newCategory) {
		return;
	}
	let response;
	try {
		response = await fetch("/api/category", {
			method: "POST",
			headers: {"Content-Type": "application/json"},
			body: JSON.stringify({id: taskId, value: newCategory, expected_chg_ts: current.chg_ts})
		});
	} catch (error) {
		banner.hidden = false;
		banner.textContent = "connection lost — retrying";
		return;
	}
	let reply = {};
	try {
		reply = await response.json();
	} catch (error) {
		reply = {};
	}
	if (response.ok) {
		apply(reply);
		return;
	}
	if (response.status === 409 && reply.task) {
		adopt(reply.task);
	}
	banner.hidden = false;
	banner.textContent = reply.message || "the move was rejected";
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
		banner.textContent = "connection lost — retrying";
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
