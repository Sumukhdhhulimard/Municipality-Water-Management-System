
const API = "http://127.0.0.1:8000";
let token = sessionStorage.getItem("token");
let role = sessionStorage.getItem("role");

const $ = id => document.getElementById(id);

function message(text, error = false) {
  $("message").textContent = text;
  $("message").className = error ? "error" : "success";
}

async function request(path, method = "GET", body = null) {
  const headers = {};
  if (body !== null) headers["Content-Type"] = "application/json";
  if (token) headers.Authorization = `Bearer ${token}`;

  const response = await fetch(API + path, {
    method,
    headers,
    body: body === null ? null : JSON.stringify(body)
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(
      typeof data.detail === "string"
        ? data.detail : JSON.stringify(data.detail)
    );
  }
  return data;
}

async function run(action) {
  try {
    await action();
  } catch (err) {
    message(err.message, true);
  }
}

function formData(form) {
  return Object.fromEntries(new FormData(form).entries());
}


function table(target, records, columns, actions = []) {
  const root = $(target);

  if (!root) {
    console.error("Missing table element:", target);
    return;
  }

  if (!Array.isArray(records)) {
    console.error("Invalid records:", target, records);
    root.textContent = "Unable to display records.";
    return;
  }

  if (!Array.isArray(actions)) {
    console.error("Invalid table actions:", actions);
    actions = [];
  }

  root.replaceChildren();

  if (!records.length) {
    root.textContent = "No records found.";
    return;
  }

  const t = document.createElement("table");
  const head = t.createTHead().insertRow();

  [...columns.map(c => c[0]), ...actions.map(a => a.label)]
    .forEach(label => {
      const th = document.createElement("th");
      th.textContent = label;
      head.append(th);
    });

  const tbody = t.createTBody();

  records.forEach(record => {
    const tr = tbody.insertRow();

    columns.forEach(([, key]) => {
      const td = tr.insertCell();
      const value = record[key];
      td.textContent = value == null ? "-" : String(value);
    });

    actions.forEach(action => {
      const td = tr.insertCell();
      if (action.show && !action.show(record)) return;
      const button = document.createElement("button");
      button.textContent = action.label;
      button.onclick = () => run(() => action.click(record));
      td.append(button);
    });
  });

  root.append(t);
}

function showPage() {
  $("auth").hidden = !!token;
  $("resident").hidden = !token || role !== "resident";
  $("operator").hidden = !token || role !== "operator";
  $("logout").hidden = !token;

  $("aiPanel").hidden = !token;

  updateRoleNavigation();

}

async function loadLocations() {
  const locations = await request("/locations");
  const select = $("roads");

  locations.forEach(loc => {
    const option = document.createElement("option");
    option.value = loc.road_id;
    option.textContent = `${loc.zone_name} - ${loc.road_name}`;
    select.append(option);
  });
}

$("registerForm").onsubmit = event => {
  event.preventDefault();
  run(async () => {
    const data = formData(event.target);
    data.road_id = Number(data.road_id);
    const result = await request("/register", "POST", data);
    message(`Account created. Resident ID: ${result.resident_id}`);
    event.target.reset();
  });
};

$("loginForm").onsubmit = event => {
  event.preventDefault();
  run(async () => {
    const data = formData(event.target);
    const result = await request("/login", "POST", data);

    token = result.access_token;
    role = result.role;
    sessionStorage.setItem("token", token);
    sessionStorage.setItem("role", role);

    showPage();
    await loadDashboard();
    message("Login successful");
  });
};

$("logout").onclick = () => {
  token = null;
  role = null;
  sessionStorage.clear();
  showPage();
  message("Logged out");
};

async function loadDashboard() {
  if (role === "resident") await loadResident();
  if (role === "operator") await loadOperator();
}

async function loadResident() {
  const [profile, connections, bills, payments, complaints] =
    await Promise.all([
      request("/resident/dashboard"),
      request("/resident/connections"),
      request("/resident/bills"),
      request("/resident/payments"),
      request("/resident/complaints")
    ]);

  $("profile").textContent =
    `Welcome, ${profile.full_name} | Resident ID: ${profile.resident_id}`;

  table("connections", connections, [
    ["Connection ID", "connection_id"],
    ["Type", "connection_type"],
    ["Status", "status"]
  ]);

  table("bills", bills, [
    ["Bill ID", "bill_id"],
    ["Month", "billing_month"],
    ["Units", "units_consumed"],
    ["Amount (INR)", "amount"],
    ["Due Date", "due_date"],
    ["Status", "status"]
  ], [{
    label: "Pay",
    show: b => b.status === "Unpaid",
    click: async b => {
      if (!confirm(`Simulate payment of INR ${b.amount}?`)) return;
      await request(`/resident/bills/${b.bill_id}/pay`, "POST", {
        method: "Demo"
      });
      message("Simulated payment successful");
      await loadResident();
    }
  }]);

  table("myPayments", payments, [
    ["Payment ID", "payment_id"],
    ["Bill ID", "bill_id"],
    ["Amount", "amount"],
    ["Method", "payment_method"],
    ["Reference", "transaction_reference"]
  ]);

  table("myComplaints", complaints, [
    ["Complaint ID", "complaint_id"],
    ["Category", "category"],
    ["Description", "description"],
    ["Status", "status"]
  ]);
}

$("requestConnection").onclick = () => run(async () => {
  await request("/resident/connections", "POST", {
    connection_type: "Domestic"
  });
  message("Water connection request submitted");
  await loadResident();
});

$("complaintForm").onsubmit = event => {
  event.preventDefault();
  run(async () => {
    await request("/resident/complaints", "POST",
                  formData(event.target));
    event.target.reset();
    message("Complaint submitted");
    await loadResident();
  });

if (role === "resident") {
  $("residentNav").hidden = false;
}

};

async function loadOperator() {
  const [dashboard, connections, complaints,
         payments, zones, residents] = await Promise.all([
    request("/operator/dashboard"),
    request("/operator/connections"),
    request("/operator/complaints"),
    request("/operator/payments"),
    request("/operator/zones"),
    request("/operator/residents")
  ]);

  const stats = $("statistics");
  stats.replaceChildren();

  Object.entries(dashboard.stats).forEach(([key, value]) => {
    const card = document.createElement("div");
    card.className = "stat";

    const label = document.createElement("span");
    label.textContent = key.replaceAll("_", " ");

    const number = document.createElement("strong");
    number.textContent = value;

    card.append(label, number);
    stats.append(card);
  });

  table("operatorConnections", connections, [
    ["Connection ID", "connection_id"],
    ["Resident", "full_name"],
    ["Type", "connection_type"],
    ["Status", "status"]
  ],  ["Approved", "Rejected"].map(status => ({
    label: status,
    show: c => c.status === "Pending",
    click: async c => {
      await request(
        `/operator/connections/${c.connection_id}`,
        "PATCH", {status}
      );
      message(`Connection ${status}`);
      await loadOperator();
    }
  })));

  table("operatorComplaints", complaints, [
    ["ID", "complaint_id"],
    ["Resident", "full_name"],
    ["Category", "category"],
    ["Description", "description"],
    ["Status", "status"]
  ], ["In Progress", "Resolved"].map(status => ({
    label: status,
    show: c => c.status !== status,
    click: async c => {
      await request(
        `/operator/complaints/${c.complaint_id}`,
        "PATCH", {status}
      );
      message("Complaint status updated");
      await loadOperator();
    }
  })));

  table("operatorPayments", payments, [
    ["Payment ID", "payment_id"],
    ["Resident", "full_name"],
    ["Bill ID", "bill_id"],
    ["Amount", "amount"],
    ["Reference", "transaction_reference"]
  ]);

await loadOperatorBills();

  table("zoneStatistics", zones, [
    ["Zone", "zone_name"],
    ["Complaints", "total_complaints"],
    ["Open", "open_complaints"]
  ]);

  table("operatorResidents", residents, [
    ["ID", "resident_id"],
    ["Name", "full_name"],
    ["Email", "email"],
    ["Road", "road_name"],
    ["Zone", "zone_name"]
  ]);
}

showPage();
run(async () => {
  await loadLocations();
  if (token) await loadDashboard();
});

const residentPanels = [
  "profilePanel",
  "connectionsPanel",
  "billsPanel",
  "paymentsPanel",
  "complaintsPanel"
];

const operatorPanels = [
  "statisticsPanel",
  "operatorConnectionsPanel",
  "operatorBillsPanel",
  "operatorComplaintsPanel",
  "operatorPaymentsPanel",
  "zonePanel",
  "operatorResidentsPanel"
];

function showRoleSection(target) {
  const panels = role === "resident"
    ? residentPanels : operatorPanels;

  panels.forEach(id => {
    const element = $(id);
    if (element) element.hidden = id !== target;
  });
}

function updateRoleNavigation() {
  $("residentNav").hidden = !token || role !== "resident";
  $("operatorNav").hidden = !token || role !== "operator";

  if (token && role === "resident") {
    showRoleSection("profilePanel");
  } else if (token && role === "operator") {
    showRoleSection("statisticsPanel");
  }
}


document.querySelectorAll(
  ".role-nav button"
).forEach(button => {
  button.addEventListener("click", function () {
    const target = this.dataset.target;

    console.log("Opening panel:", target);

    showRoleSection(target);
  });
});


$("generateBillForm").onsubmit = event => {
  event.preventDefault();

  run(async () => {
    const data = formData(event.target);

    data.connection_id = Number(data.connection_id);
    data.units_consumed = Number(data.units_consumed);
    data.billing_month += "-01";

    const result = await request(
      "/operator/generate-bill",
      "POST",
      data
    );

    message(
      `Bill ${result.bill_id} generated. Amount: INR ${result.amount}`
    );

    event.target.reset();
    await loadOperator();
    showRoleSection("operatorBillsPanel");
  });
};

async function loadOperatorBills() {
  const bills = await request("/operator/bills");

  table("operatorBills", bills, [
    ["Bill ID", "bill_id"],
    ["Connection", "connection_id"],
    ["Resident", "full_name"],
    ["Month", "billing_month"],
    ["Units", "units_consumed"],
    ["Amount", "amount"],
    ["Status", "status"]
  ]);
}

$("aiForm").onsubmit = event => {
  event.preventDefault();

  run(async () => {
    const question = $("aiQuestion").value.trim();

    const result = await request("/ai/ask", "POST", {
      question
    });

    $("aiAnswer").replaceChildren();

    const answer = document.createElement("p");
    answer.textContent = result.answer;
    $("aiAnswer").append(answer);

    if (result.sources.length) {
      const heading = document.createElement("strong");
      heading.textContent = "Related knowledge:";
      $("aiAnswer").append(heading);

      const list = document.createElement("ul");

      result.sources.forEach(source => {
        const item = document.createElement("li");
        item.textContent =
          `${source.title} (${source.similarity})`;
        list.append(item);
      });

      $("aiAnswer").append(list);
    }
  });
};

function showRoleSection(target) {
  const panels = role === "resident"
    ? residentPanels
    : role === "operator"
      ? operatorPanels
      : [];

  if (!panels.includes(target)) return;

  panels.forEach(id => {
    const element = document.getElementById(id);

    if (element) {
      element.hidden = (id !== target);
    }
  });

  document.querySelectorAll(
    ".role-nav button"
  ).forEach(button => {
    button.classList.toggle(
      "active",
      button.dataset.target === target
    );
  });
}

function updateRoleNavigation() {
  const residentLoggedIn =
    !!token && role === "resident";

  const operatorLoggedIn =
    !!token && role === "operator";

  $("residentNav").hidden = !residentLoggedIn;
  $("operatorNav").hidden = !operatorLoggedIn;

  if (residentLoggedIn) {
    showRoleSection("profilePanel");
  }

  if (operatorLoggedIn) {
    showRoleSection("statisticsPanel");
  }
}
