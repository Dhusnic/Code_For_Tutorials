from flask import Flask, render_template_string, request, jsonify
import re

app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Git Diff Review Tool</title>
<style>
body {
    font-family: Consolas, monospace;
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 20px;
}

textarea {
    width: 100%;
    height: 180px;
    background: #252526;
    color: #d4d4d4;
    border: 1px solid #333;
    padding: 10px;
}

button {
    background: #0e639c;
    color: white;
    border: none;
    padding: 6px 12px;
    margin: 5px;
    cursor: pointer;
}

.hunk {
    border: 1px solid #333;
    margin-top: 15px;
}

.header {
    background: #333;
    padding: 6px;
    display: flex;
    justify-content: space-between;
}

.diff {
    display: grid;
    grid-template-columns: 1fr 1fr;
}

.left, .right {
    padding: 10px;
    white-space: pre;
}

.remove { background: #5a1d1d; }
.add { background: #144212; }
.context { color: #aaa; }

.accepted { border: 2px solid #2ecc71; }
.rejected { border: 2px solid #e74c3c; }

.final {
    margin-top: 30px;
    border: 1px solid #333;
    padding: 10px;
    white-space: pre;
    background: #111;
}
</style>
</head>
<body>

<h2>🔥 Git Diff Review Tool (VS Code style)</h2>

<textarea id="diffInput" placeholder="Paste git diff here..."></textarea>
<br>
<button onclick="parseDiff()">Parse Diff</button>

<div id="hunks"></div>

<h3>Final File Output</h3>
<div id="final" class="final"></div>

<script>
let hunks = [];

function parseDiff() {
    fetch("/parse", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({diff: diffInput.value})
    })
    .then(r => r.json())
    .then(data => {
        hunks = data;
        render();
    });
}

function render() {
    const container = document.getElementById("hunks");
    container.innerHTML = "";

    hunks.forEach((h, i) => {
        const div = document.createElement("div");
        div.className = "hunk " + (h.accepted ? "accepted" : h.rejected ? "rejected" : "");

        div.innerHTML = `
            <div class="header">
                <span>${h.header}</span>
                <span>
                    <button onclick="accept(${i})">Accept</button>
                    <button onclick="reject(${i})">Reject</button>
                </span>
            </div>
            <div class="diff">
                <div class="left">${h.left}</div>
                <div class="right">${h.right}</div>
            </div>
        `;
        container.appendChild(div);
    });

    applyPatch();
}

function accept(i) {
    hunks[i].accepted = true;
    hunks[i].rejected = false;
    render();
}

function reject(i) {
    hunks[i].rejected = true;
    hunks[i].accepted = false;
    render();
}

function applyPatch() {
    fetch("/apply", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(hunks)
    })
    .then(r => r.json())
    .then(data => {
        document.getElementById("final").textContent = data.result;
    });
}
</script>

</body>
</html>
"""

# ---------------- BACKEND LOGIC ---------------- #

@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/parse", methods=["POST"])
def parse_diff():
    diff = request.json["diff"]
    hunks = []
    current = None

    for line in diff.splitlines():
        if line.startswith("@@"):
            if current:
                hunks.append(current)
            current = {
                "header": line,
                "left": "",
                "right": "",
                "accepted": False,
                "rejected": False
            }
        elif current:
            if line.startswith("-") and not line.startswith("---"):
                current["left"] += line[1:] + "\\n"
            elif line.startswith("+") and not line.startswith("+++"):
                current["right"] += line[1:] + "\\n"
            else:
                current["left"] += line + "\\n"
                current["right"] += line + "\\n"

    if current:
        hunks.append(current)

    return jsonify(hunks)


@app.route("/apply", methods=["POST"])
def apply_patch():
    hunks = request.json
    result = ""

    for h in hunks:
        if h["accepted"]:
            result += h["right"]
        else:
            result += h["left"]

    return jsonify({"result": result})


if __name__ == "__main__":
    app.run(debug=True)
