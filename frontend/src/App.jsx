import React, {useEffect, useState, useCallback} from 'react';



import AdvancedAnalytics from "./components/AdvancedAnalytics";



import IncidentManagement from "./components/IncidentManagement";



const API = (import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000').replace(/\/$/, '');

const RESIDENT_TABS = ['My Profile','Connections','Water Bills','Payments','Complaints','AI Assistant'];

const OPERATOR_TABS = ['Overview','Requests','Generate Bills','Complaints','Payments','Zones','Residents','Smart Analytics','Incident Management','AI Assistant'];

const fields = (event) => Object.fromEntries(new FormData(event.currentTarget).entries());

const list = (data) => Array.isArray(data) ? data : [];

const display = (value) => value == null ? '—' : typeof value === 'object' ? JSON.stringify(value) : String(value);



async function api(path, {method='GET', body, token}={}) {

  const headers = {};

  if (body !== undefined) headers['Content-Type'] = 'application/json';

  if (token) headers.Authorization = `Bearer ${token}`;

  let response;

  try {

    response = await fetch(`${API}${path}`, {method, headers, body: body === undefined ? undefined : JSON.stringify(body)});

  } catch {

    throw new Error(`Cannot reach the backend at ${API}. Start FastAPI and check CORS.`);

  }

  const raw = await response.text();

  let data;

  try { data = raw ? JSON.parse(raw) : {}; } catch { data = {detail:raw}; }

  if (!response.ok) {

    const detail = data?.detail;

    const msg = typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : response.statusText;

    throw new Error(`${response.status}: ${msg}`);

  }

  return data;

}



function DataTable({rows, columns, actions=[]}) {

  const records = list(rows);

  return <div className="table-scroll">{records.length === 0 ? <p className="muted">No records found.</p> :

    <table><thead><tr>{columns.map(([title])=><th key={title}>{title}</th>)}{actions.length>0&&<th>Actions</th>}</tr></thead>

    <tbody>{records.map((record,i)=><tr key={record.id ?? record.bill_id ?? record.connection_id ?? record.complaint_id ?? record.payment_id ?? record.resident_id ?? i}>

      {columns.map(([title,key])=><td key={title}>{display(typeof key === 'function' ? key(record) : record[key])}</td>)}

      {actions.length>0&&<td><div className="actions">{actions.filter(a=>!a.show || a.show(record)).map(a=><button key={a.label} className="small" disabled={a.disabled} onClick={()=>a.click(record)}>{a.label}</button>)}</div></td>}

    </tr>)}</tbody></table>}</div>;

}

function Panel({title, children}) {return <section className="panel"><h3>{title}</h3>{children}</section>}

function Notice({notice,onClose}) {return notice?.text ? <div role="alert" className={`notice ${notice.error?'error':'ok'}`}>{notice.text}<button className="dismiss" onClick={onClose} aria-label="Dismiss">×</button></div> : null}

function Nav({tabs, active, setActive}) {return <nav className="tabs" aria-label="Dashboard navigation">{tabs.map(tab=><button key={tab} className={active===tab?'active':''} onClick={()=>setActive(tab)}>{tab}</button>)}</nav>}



function App() {

  const [auth,setAuth] = useState(()=>({token:sessionStorage.getItem('token')||'',role:sessionStorage.getItem('role')||''}));

  const [active,setActive] = useState('');

  const [notice,setNotice] = useState(null);

  const [busy,setBusy] = useState(false);

  const [roads,setRoads] = useState([]);

  const [data,setData] = useState({});

  const [errors,setErrors] = useState({});

  const [aiResult,setAiResult] = useState(null);

  const [aiBusy,setAiBusy] = useState(false);

  const [search,setSearch] = useState('');

  const [selectedConnection,setSelectedConnection] = useState('');

  const [loading,setLoading] = useState(false);

  const tell = (text,error=false)=>setNotice({text,error});

  const call = useCallback((path,opts={})=>api(path,{...opts,token:auth.token}),[auth.token]);

  const logout = useCallback(()=>{sessionStorage.removeItem('token');sessionStorage.removeItem('role');setAuth({token:'',role:''});setData({});setErrors({});setActive('');tell('Logged out.');},[]);

  const tasks = auth.role==='resident' ? {

    profile:'/resident/dashboard',connections:'/resident/connections',bills:'/resident/bills',payments:'/resident/payments',complaints:'/resident/complaints'

  } : auth.role==='operator' ? {

    overview:'/operator/dashboard',connections:'/operator/connections',bills:'/operator/bills',complaints:'/operator/complaints',payments:'/operator/payments',zones:'/operator/zones',residents:'/operator/residents'

  } : {};

  const refresh = useCallback(async()=>{

    if (!auth.token || !['resident','operator'].includes(auth.role)) return;

    setLoading(true);

    const entries=Object.entries(tasks);

    const results=await Promise.allSettled(entries.map(([,path])=>call(path)));

    const next={}, errs={};

    results.forEach((result,i)=>{

      const name=entries[i][0];

      if(result.status==='fulfilled') next[name]=result.value;

      else errs[name]=result.reason.message;

    });

    setData(next);setErrors(errs);setLoading(false);

    if(Object.keys(errs).length) tell(`Some sections could not load: ${Object.keys(errs).join(', ')}.`,true);

  },[auth.token,auth.role,call]);

  useEffect(()=>{api('/locations').then(v=>setRoads(list(v))).catch(e=>tell(e.message,true));},[]);

  useEffect(()=>{setActive(auth.role==='operator'?'Overview':'My Profile');if(auth.token) refresh();},[auth.token,auth.role,refresh]);

  async function execute(fn){setBusy(true);try{await fn();}catch(e){tell(e.message,true);}finally{setBusy(false);}}

  async function login(e){e.preventDefault();const values=fields(e);await execute(async()=>{

    const result=await api('/login',{method:'POST',body:values});

    if(!['resident','operator'].includes(result.role)||!result.access_token) throw new Error('Unexpected login response.');

    sessionStorage.setItem('token',result.access_token);sessionStorage.setItem('role',result.role);

    setAuth({token:result.access_token,role:result.role});tell('Login successful.');

  });}

  async function register(e){e.preventDefault();const form=e.currentTarget;const values=fields(e);values.road_id=Number(values.road_id);

    await execute(async()=>{const result=await api('/register',{method:'POST',body:values});tell(`Account created. Resident ID: ${result.resident_id}`);form.reset();});}

  async function mutate(path,method,body,success){await execute(async()=>{await call(path,{method,body});tell(success);await refresh();});}

  async function generateBill(e){e.preventDefault();const form=e.currentTarget;const values=fields(e);

    values.connection_id=Number(values.connection_id);values.units_consumed=Number(values.units_consumed);values.billing_month += '-01';

    await execute(async()=>{const result=await call('/operator/generate-bill',{method:'POST',body:values});tell(`Bill ${result.bill_id} generated. Amount: INR ${result.amount}`);form.reset();setSelectedConnection('');await refresh();});}

  async function complaint(e){e.preventDefault();const form=e.currentTarget;await execute(async()=>{await call('/resident/complaints',{method:'POST',body:fields(e)});form.reset();tell('Complaint submitted.');await refresh();});}

  async function askAI(e){e.preventDefault();const question=fields(e).question?.trim();if(!question)return;setAiBusy(true);setAiResult(null);

    try{const result=await call('/ai/ask',{method:'POST',body:{question}});setAiResult(result);}catch(err){tell(err.message,true);}finally{setAiBusy(false);}}

  const status = name=>errors[name] ? <p className="inline-error">{errors[name]}</p> : null;

  const connectionsColumns=[['Connection ID','connection_id'],['Type','connection_type'],['Status','status']];

  const billColumns=[['Bill ID','bill_id'],['Month','billing_month'],['Units','units_consumed'],['Amount (INR)','amount'],['Due Date','due_date'],['Status','status']];

  const complaintColumns=[['Complaint ID','complaint_id'],['Category','category'],['Description','description'],['Status','status']];

  const approvedConnections=list(data.connections).filter(c=>String(c.status).toLowerCase()==='approved');

  const filteredResidents=list(data.residents).filter(r=>[r.full_name,r.email,r.resident_id,r.road_name,r.zone_name].some(v=>String(v??'').toLowerCase().includes(search.toLowerCase())));

  const paymentColumns=[['Payment ID','payment_id'],['Bill ID','bill_id'],['Amount','amount'],['Method','payment_method'],['Reference','transaction_reference']];

  const ai=<Panel title="Water Management AI Assistant"><p className="muted">Ask about connections, bills, complaints, and water conservation.</p><form onSubmit={askAI}><textarea name="question" placeholder="How do I request a water connection?" required minLength="3"/><button disabled={aiBusy}>{aiBusy?'Searching…':'Ask Assistant'}</button></form>{aiResult&&<div className="answer"><h4>Answer</h4><p>{display(aiResult.answer)}</p>{Array.isArray(aiResult.sources)&&aiResult.sources.length>0&&<><h4>Related knowledge</h4><ul>{aiResult.sources.map((s,i)=><li key={i}>{display(s.title)} {s.similarity!=null?`(${display(s.similarity)})`:''}</li>)}</ul></>}</div>}</Panel>;

  return <><header className="topbar"><div><h1>Bengaluru Municipal Water Management System</h1><span>Municipality Water Management System</span></div>{auth.token&&<button className="logout" onClick={logout}>Logout</button>}</header>

    <main><Notice notice={notice} onClose={()=>setNotice(null)}/>

    {!auth.token ? <div className="auth-grid"><Panel title="Login"><form onSubmit={login}><label>Email<input name="email" type="email" required placeholder="Email address"/></label><label>Password<input name="password" type="password" required placeholder="Password"/></label><button disabled={busy}>Login</button></form></Panel>

      <Panel title="New Resident Registration"><form onSubmit={register}><label>Full name<input name="full_name" required/></label><label>Email<input name="email" type="email" required/></label><label>Password<input name="password" type="password" minLength="8" required/></label><label>Phone<input name="phone"/></label><label>House number<input name="house_number"/></label><label>Road<select name="road_id" required defaultValue=""><option value="">Select road</option>{roads.map(r=><option key={r.road_id} value={r.road_id}>{r.zone_name} - {r.road_name}</option>)}</select></label><button disabled={busy}>Create Account</button></form></Panel></div>

    : <><div className="dashboard-head"><div><p className="eyebrow">{auth.role==='resident'?'RESIDENT PORTAL':'OPERATOR PORTAL'}</p><h2>{auth.role==='resident'?'Resident Dashboard':'Operator Dashboard'}</h2></div><button className="secondary" onClick={()=>execute(refresh)} disabled={busy||loading}>{loading?'Loading…':'Refresh Data'}</button></div>

    <Nav tabs={auth.role==='resident'?RESIDENT_TABS:OPERATOR_TABS} active={active} setActive={setActive}/>

    {auth.role==='resident'&&<>

      {active==='My Profile'&&<Panel title="My Profile">{status('profile')}<div className="profile-grid">{data.profile ? Object.entries({Name:data.profile.full_name,'Resident ID':data.profile.resident_id,Email:data.profile.email,Phone:data.profile.phone,House:data.profile.house_number,Road:data.profile.road_name,Zone:data.profile.zone_name,City:'Bengaluru'}).map(([key,value])=><div className="profile-field" key={key}><span>{key}</span><strong>{display(value)}</strong></div>) : <p>Profile unavailable.</p>}</div></Panel>}

      {active==='Connections'&&<Panel title="Water Connections">{status('connections')}<button disabled={busy} onClick={()=>mutate('/resident/connections','POST',{connection_type:'Domestic'},'Connection request submitted.')}>Request New Connection</button><DataTable rows={data.connections} columns={connectionsColumns}/><p className="hint">An existing active or pending connection may cause a 409 conflict. This is a backend validation rule.</p></Panel>}

      {active==='Water Bills'&&<Panel title="My Water Bills">{status('bills')}<DataTable rows={data.bills} columns={billColumns} actions={[{label:'Pay (Demo)',show:b=>String(b.status).toLowerCase()==='unpaid',disabled:busy,click:b=>{if(window.confirm(`Simulate payment of INR ${b.amount}?`))mutate(`/resident/bills/${b.bill_id}/pay`,'POST',{method:'Demo'},'Simulated payment successful.');}}]}/></Panel>}

      {active==='Payments'&&<Panel title="My Payments">{status('payments')}<DataTable rows={data.payments} columns={paymentColumns}/></Panel>}

      {active==='Complaints'&&<><Panel title="Submit Complaint"><form onSubmit={complaint}><label>Category<select name="category">{['Leakage','Low Pressure','Water Quality','Billing Issue','Other'].map(c=><option key={c}>{c}</option>)}</select></label><label>Description<textarea name="description" minLength="5" required placeholder="Describe your complaint"/></label><button disabled={busy}>Submit Complaint</button></form></Panel><Panel title="Complaint History">{status('complaints')}<DataTable rows={data.complaints} columns={complaintColumns}/></Panel></>}

    </>}

    {auth.role==='operator'&&<>

      {active==='Overview'&&<Panel title="City Overview">{status('overview')}<div className="stats">{Object.entries(data.overview?.stats||{}).map(([key,value])=><div className="stat" key={key}><span>{key.replaceAll('_',' ')}</span><strong>{display(value)}</strong></div>)}</div>{!data.overview?.stats&&<p className="muted">No statistics available.</p>}</Panel>}

      {active==='Requests'&&<Panel title="Connection Requests">{status('connections')}<DataTable rows={data.connections} columns={[['Connection ID','connection_id'],['Resident','full_name'],['Type','connection_type'],['Status','status']]} actions={['Approved','Rejected'].map(s=>({label:s,disabled:busy,show:r=>String(r.status).toLowerCase()==='pending',click:r=>mutate(`/operator/connections/${r.connection_id}`,'PATCH',{status:s},`Connection ${s.toLowerCase()}.`)}))}/></Panel>}

      {active==='Generate Bills'&&<><Panel title="Generate Monthly Water Bill"><form onSubmit={generateBill}><label>Connection ID<select name="connection_id" value={selectedConnection} onChange={e=>setSelectedConnection(e.target.value)} required><option value="">Select an approved connection</option>{approvedConnections.map(c=><option key={c.connection_id} value={c.connection_id}>#{c.connection_id} — {display(c.full_name)} ({display(c.connection_type)})</option>)}</select></label><label>Billing Month<input name="billing_month" type="month" required/></label><label>Water Consumption (Units)<input name="units_consumed" type="number" min="0" max="100000" step="0.01" required/></label><button disabled={busy}>Generate Bill</button></form></Panel><Panel title="All Generated Bills">{status('bills')}<DataTable rows={data.bills} columns={[['Bill ID','bill_id'],['Connection','connection_id'],['Resident','full_name'],['Month','billing_month'],['Units','units_consumed'],['Amount','amount'],['Status','status']]}/></Panel></>}

      {active==='Complaints'&&<Panel title="Complaints Management">{status('complaints')}<DataTable rows={data.complaints} columns={[['ID','complaint_id'],['Resident','full_name'],['Category','category'],['Description','description'],['Status','status']]} actions={['In Progress','Resolved'].map(s=>({label:s,disabled:busy,show:r=>String(r.status).toLowerCase()!==s.toLowerCase(),click:r=>mutate(`/operator/complaints/${r.complaint_id}`,'PATCH',{status:s},'Complaint updated.')}))}/></Panel>}

      {active==='Payments'&&<Panel title="Payment Records">{status('payments')}<DataTable rows={data.payments} columns={[['Payment ID','payment_id'],['Resident','full_name'],['Bill ID','bill_id'],['Amount','amount'],['Reference','transaction_reference']]}/></Panel>}

      {active==='Zones'&&<Panel title="Zone Statistics">{status('zones')}<DataTable rows={data.zones} columns={[['Zone','zone_name'],['Complaints','total_complaints'],['Open','open_complaints']]}/></Panel>}

      {active==='Residents'&&<Panel title="Registered Residents">{status('residents')}<label className="search-label">Search residents<input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search name, email, ID, road or zone"/></label><p className="muted">Showing {filteredResidents.length} residents</p><DataTable rows={filteredResidents} columns={[['ID','resident_id'],['Name','full_name'],['Email','email'],['Connection ID',r=>r.connection_id ?? (list(data.connections).filter(c=>c.resident_id===r.resident_id).map(c=>c.connection_id).join(', ') || '—')],['Road','road_name'],['Zone','zone_name']]}/></Panel>}
      {active === 'Smart Analytics' && (
  <AdvancedAnalytics token={auth.token} />
)}

{active === 'Incident Management' && (
  <IncidentManagement token={auth.token} />
)}
    </>}

    {auth.role==='operator' && active==='Smart Analytics' && <AdvancedAnalytics token={auth.token} />}
    {auth.role==='operator' && active==='Incident Management' && <IncidentManagement token={auth.token} />}
    {active==='AI Assistant'&&ai}</>}

    </main></>;

}



export default App;
