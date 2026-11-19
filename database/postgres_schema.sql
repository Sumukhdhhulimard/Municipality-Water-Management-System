--
-- PostgreSQL database dump
--

\restrict ISh5UZncHMo72yY5IiY3UYL6AOUiqTnaj0qMSQloLAmV1WeO1qEGy1orqkBrNi8

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: smart_water; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA smart_water;


--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: audit_bill_status(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.audit_bill_status() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO bill_audit(
            bill_id, old_status, new_status
        )
        VALUES (
            NEW.bill_id, OLD.status, NEW.status
        );
    END IF;

    RETURN NEW;
END;
$$;


--
-- Name: calculate_water_bill(numeric); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.calculate_water_bill(p_units numeric) RETURNS numeric
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF p_units IS NULL OR p_units < 0 THEN
        RAISE EXCEPTION 'Invalid consumption units';
    END IF;

    RETURN ROUND(p_units * 12, 2);
END;
$$;


--
-- Name: pay_water_bill(integer, character varying, character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pay_water_bill(p_bill_id integer, p_method character varying, p_reference character varying) RETURNS integer
    LANGUAGE plpgsql
    AS $$
DECLARE
    v_amount NUMERIC(10,2);
    v_status VARCHAR(20);
    v_payment_id INTEGER;
BEGIN
    SELECT amount, status
    INTO v_amount, v_status
    FROM public.bills
    WHERE bill_id = p_bill_id
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Bill % not found', p_bill_id;
    END IF;

    IF LOWER(TRIM(v_status)) = 'paid' THEN
        RAISE EXCEPTION 'Bill % already paid', p_bill_id;
    END IF;

    IF LOWER(TRIM(v_status)) <> 'unpaid' THEN
        RAISE EXCEPTION 'Bill % has invalid status %',
            p_bill_id, v_status;
    END IF;

    INSERT INTO public.payments (
        bill_id,
        amount,
        payment_method,
        transaction_reference
    )
    VALUES (
        p_bill_id,
        v_amount,
        p_method,
        p_reference
    )
    RETURNING payment_id INTO v_payment_id;

    UPDATE public.bills
    SET status = 'Paid'
    WHERE bill_id = p_bill_id;

    RETURN v_payment_id;
END;
$$;


--
-- Name: set_bill_amount(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_bill_amount() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.amount :=
        calculate_water_bill(NEW.units_consumed);
    RETURN NEW;
END;
$$;


--
-- Name: audit_incident_change(); Type: FUNCTION; Schema: smart_water; Owner: -
--

CREATE FUNCTION smart_water.audit_incident_change() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO smart_water.incident_outbox (
            incident_id, event_type, payload
        )
        VALUES (
            NEW.incident_id,
            'INCIDENT_CREATED',
            jsonb_build_object(
                'status', NEW.status,
                'zone_id', NEW.zone_id,
                'severity', NEW.severity,
                'description', NEW.description
            )
        );

    ELSIF NEW.status IS DISTINCT FROM OLD.status THEN
        INSERT INTO smart_water.incident_outbox (
            incident_id, event_type, payload
        )
        VALUES (
            NEW.incident_id,
            'STATUS_CHANGED',
            jsonb_build_object(
                'old_status', OLD.status,
                'new_status', NEW.status
            )
        );
    END IF;

    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: bill_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bill_audit (
    audit_id bigint NOT NULL,
    bill_id integer NOT NULL,
    old_status character varying(20),
    new_status character varying(20),
    changed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: bill_audit_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bill_audit_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bill_audit_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bill_audit_audit_id_seq OWNED BY public.bill_audit.audit_id;


--
-- Name: bills; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.bills (
    bill_id integer NOT NULL,
    connection_id integer NOT NULL,
    billing_month date NOT NULL,
    units_consumed numeric(10,2) NOT NULL,
    amount numeric(10,2) NOT NULL,
    due_date date NOT NULL,
    status character varying(20) DEFAULT 'Unpaid'::character varying,
    CONSTRAINT bills_amount_check CHECK ((amount >= (0)::numeric)),
    CONSTRAINT bills_status_check CHECK (((status)::text = ANY ((ARRAY['Paid'::character varying, 'Unpaid'::character varying])::text[]))),
    CONSTRAINT bills_units_consumed_check CHECK ((units_consumed >= (0)::numeric))
);


--
-- Name: bills_bill_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.bills_bill_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: bills_bill_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.bills_bill_id_seq OWNED BY public.bills.bill_id;


--
-- Name: complaints; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.complaints (
    complaint_id integer NOT NULL,
    resident_id integer NOT NULL,
    connection_id integer,
    category character varying(50) NOT NULL,
    description text NOT NULL,
    status character varying(20) DEFAULT 'Open'::character varying,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT complaints_status_check CHECK (((status)::text = ANY ((ARRAY['Open'::character varying, 'In Progress'::character varying, 'Resolved'::character varying])::text[])))
);


--
-- Name: complaints_complaint_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.complaints_complaint_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: complaints_complaint_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.complaints_complaint_id_seq OWNED BY public.complaints.complaint_id;


--
-- Name: operators; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.operators (
    operator_id integer NOT NULL,
    full_name character varying(100) NOT NULL,
    email character varying(150) NOT NULL,
    password_hash text NOT NULL,
    zone_id integer
);


--
-- Name: operators_operator_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.operators_operator_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: operators_operator_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.operators_operator_id_seq OWNED BY public.operators.operator_id;


--
-- Name: payments; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.payments (
    payment_id integer NOT NULL,
    bill_id integer NOT NULL,
    amount numeric(10,2) NOT NULL,
    paid_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    payment_method character varying(30),
    transaction_reference character varying(100),
    CONSTRAINT payments_amount_check CHECK ((amount > (0)::numeric))
);


--
-- Name: payments_payment_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.payments_payment_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: payments_payment_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.payments_payment_id_seq OWNED BY public.payments.payment_id;


--
-- Name: residents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.residents (
    resident_id integer NOT NULL,
    full_name character varying(100) NOT NULL,
    email character varying(150) NOT NULL,
    password_hash text NOT NULL,
    phone character varying(15),
    road_id integer,
    house_number character varying(20),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: residents_resident_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.residents_resident_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: residents_resident_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.residents_resident_id_seq OWNED BY public.residents.resident_id;


--
-- Name: review_assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.review_assets (
    asset_id integer NOT NULL,
    asset_code character varying(50) NOT NULL,
    zone_id integer,
    purchase_cost numeric(12,2),
    status character varying(20) DEFAULT 'ACTIVE'::character varying,
    description text,
    CONSTRAINT chk_asset_status CHECK (((status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'REPAIR'::character varying, 'RETIRED'::character varying])::text[]))),
    CONSTRAINT review_assets_purchase_cost_check CHECK ((purchase_cost >= (0)::numeric))
);


--
-- Name: review_assets_asset_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.review_assets ALTER COLUMN asset_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.review_assets_asset_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: roads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.roads (
    road_id integer NOT NULL,
    zone_id integer NOT NULL,
    road_name character varying(100) NOT NULL
);


--
-- Name: roads_road_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.roads_road_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: roads_road_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.roads_road_id_seq OWNED BY public.roads.road_id;


--
-- Name: water_connections; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.water_connections (
    connection_id integer NOT NULL,
    resident_id integer NOT NULL,
    connection_type character varying(20) DEFAULT 'Domestic'::character varying,
    status character varying(20) DEFAULT 'Pending'::character varying,
    requested_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT water_connections_status_check CHECK (((status)::text = ANY ((ARRAY['Pending'::character varying, 'Approved'::character varying, 'Rejected'::character varying])::text[])))
);


--
-- Name: vw_resident_billing; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_resident_billing AS
 SELECT r.resident_id,
    r.full_name,
    count(b.bill_id) AS total_bills,
    COALESCE(sum(b.amount), (0)::numeric) AS total_billed,
    COALESCE(sum(b.amount) FILTER (WHERE ((b.status)::text = 'Unpaid'::text)), (0)::numeric) AS unpaid_amount
   FROM ((public.residents r
     LEFT JOIN public.water_connections c ON ((c.resident_id = r.resident_id)))
     LEFT JOIN public.bills b ON ((b.connection_id = c.connection_id)))
  GROUP BY r.resident_id, r.full_name;


--
-- Name: vw_unpaid_bills; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_unpaid_bills AS
 SELECT b.bill_id,
    r.resident_id,
    r.full_name,
    b.amount,
    b.due_date
   FROM ((public.bills b
     JOIN public.water_connections c ON ((b.connection_id = c.connection_id)))
     JOIN public.residents r ON ((c.resident_id = r.resident_id)))
  WHERE ((b.status)::text = 'Unpaid'::text);


--
-- Name: zones; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.zones (
    zone_id integer NOT NULL,
    zone_name character varying(100) NOT NULL
);


--
-- Name: vw_zone_complaint_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_zone_complaint_summary AS
 SELECT z.zone_id,
    z.zone_name,
    count(cp.complaint_id) AS total_complaints,
    count(cp.complaint_id) FILTER (WHERE ((cp.status)::text = 'Open'::text)) AS open_complaints,
    count(cp.complaint_id) FILTER (WHERE ((cp.status)::text = 'Resolved'::text)) AS resolved_complaints
   FROM (((public.zones z
     LEFT JOIN public.roads rd ON ((rd.zone_id = z.zone_id)))
     LEFT JOIN public.residents r ON ((r.road_id = rd.road_id)))
     LEFT JOIN public.complaints cp ON ((cp.resident_id = r.resident_id)))
  GROUP BY z.zone_id, z.zone_name;


--
-- Name: vw_zone_complaints; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_zone_complaints AS
 SELECT z.zone_id,
    z.zone_name,
    count(cp.complaint_id) AS total_complaints,
    count(cp.complaint_id) FILTER (WHERE ((cp.status)::text = 'Open'::text)) AS open_complaints
   FROM (((public.zones z
     LEFT JOIN public.roads rd ON ((rd.zone_id = z.zone_id)))
     LEFT JOIN public.residents r ON ((r.road_id = rd.road_id)))
     LEFT JOIN public.complaints cp ON ((cp.resident_id = r.resident_id)))
  GROUP BY z.zone_id, z.zone_name;


--
-- Name: water_connections_connection_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.water_connections_connection_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: water_connections_connection_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.water_connections_connection_id_seq OWNED BY public.water_connections.connection_id;


--
-- Name: water_knowledge; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.water_knowledge (
    knowledge_id bigint NOT NULL,
    title character varying(200) NOT NULL,
    category character varying(100) NOT NULL,
    content text NOT NULL,
    embedding public.vector(384),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: water_knowledge_knowledge_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.water_knowledge_knowledge_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: water_knowledge_knowledge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.water_knowledge_knowledge_id_seq OWNED BY public.water_knowledge.knowledge_id;


--
-- Name: zones_zone_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.zones_zone_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: zones_zone_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.zones_zone_id_seq OWNED BY public.zones.zone_id;


--
-- Name: complaint_embeddings; Type: TABLE; Schema: smart_water; Owner: -
--

CREATE TABLE smart_water.complaint_embeddings (
    complaint_id bigint NOT NULL,
    embedding public.vector(384) NOT NULL,
    source_text text NOT NULL,
    model_name character varying(100) DEFAULT 'all-MiniLM-L6-v2'::character varying NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: incident_embeddings; Type: TABLE; Schema: smart_water; Owner: -
--

CREATE TABLE smart_water.incident_embeddings (
    incident_id bigint NOT NULL,
    embedding public.vector(384) NOT NULL,
    source_text text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: incident_outbox; Type: TABLE; Schema: smart_water; Owner: -
--

CREATE TABLE smart_water.incident_outbox (
    event_id bigint NOT NULL,
    incident_id bigint NOT NULL,
    event_type character varying(40) NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    delivered_at timestamp with time zone,
    attempts integer DEFAULT 0 NOT NULL
);


--
-- Name: incident_outbox_event_id_seq; Type: SEQUENCE; Schema: smart_water; Owner: -
--

ALTER TABLE smart_water.incident_outbox ALTER COLUMN event_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME smart_water.incident_outbox_event_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: incidents; Type: TABLE; Schema: smart_water; Owner: -
--

CREATE TABLE smart_water.incidents (
    incident_id bigint NOT NULL,
    zone_id integer NOT NULL,
    incident_type character varying(50) NOT NULL,
    severity character varying(20) DEFAULT 'MEDIUM'::character varying NOT NULL,
    description text NOT NULL,
    source character varying(30) DEFAULT 'SENSOR'::character varying NOT NULL,
    source_event_id character varying(100),
    status character varying(25) DEFAULT 'OPEN'::character varying NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    CONSTRAINT chk_incident_severity CHECK (((severity)::text = ANY ((ARRAY['LOW'::character varying, 'MEDIUM'::character varying, 'HIGH'::character varying, 'CRITICAL'::character varying])::text[]))),
    CONSTRAINT chk_incident_status CHECK (((status)::text = ANY ((ARRAY['OPEN'::character varying, 'ASSIGNED'::character varying, 'IN_PROGRESS'::character varying, 'RESOLVED'::character varying])::text[])))
);


--
-- Name: incidents_incident_id_seq; Type: SEQUENCE; Schema: smart_water; Owner: -
--

ALTER TABLE smart_water.incidents ALTER COLUMN incident_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME smart_water.incidents_incident_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: meter_readings; Type: TABLE; Schema: smart_water; Owner: -
--

CREATE TABLE smart_water.meter_readings (
    reading_id bigint NOT NULL,
    meter_id bigint NOT NULL,
    reading_time timestamp with time zone NOT NULL,
    cumulative_liters numeric(14,2) NOT NULL,
    flow_rate_lpm numeric(10,2),
    source character varying(20) DEFAULT 'SIMULATED'::character varying NOT NULL,
    CONSTRAINT chk_cumulative_liters CHECK ((cumulative_liters >= (0)::numeric)),
    CONSTRAINT chk_flow_rate CHECK (((flow_rate_lpm IS NULL) OR (flow_rate_lpm >= (0)::numeric))),
    CONSTRAINT chk_reading_source CHECK (((source)::text = ANY ((ARRAY['SIMULATED'::character varying, 'MANUAL'::character varying, 'DEVICE'::character varying])::text[])))
);


--
-- Name: meter_readings_reading_id_seq; Type: SEQUENCE; Schema: smart_water; Owner: -
--

ALTER TABLE smart_water.meter_readings ALTER COLUMN reading_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME smart_water.meter_readings_reading_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: meters; Type: TABLE; Schema: smart_water; Owner: -
--

CREATE TABLE smart_water.meters (
    meter_id bigint NOT NULL,
    meter_serial character varying(80) NOT NULL,
    connection_id bigint NOT NULL,
    installed_at timestamp with time zone DEFAULT now() NOT NULL,
    meter_status character varying(20) DEFAULT 'ACTIVE'::character varying NOT NULL,
    last_reading_at timestamp with time zone,
    CONSTRAINT chk_meter_status CHECK (((meter_status)::text = ANY ((ARRAY['ACTIVE'::character varying, 'INACTIVE'::character varying, 'FAULTY'::character varying, 'REPLACED'::character varying])::text[])))
);


--
-- Name: meters_meter_id_seq; Type: SEQUENCE; Schema: smart_water; Owner: -
--

ALTER TABLE smart_water.meters ALTER COLUMN meter_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME smart_water.meters_meter_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: technicians; Type: TABLE; Schema: smart_water; Owner: -
--

CREATE TABLE smart_water.technicians (
    technician_id bigint NOT NULL,
    full_name character varying(120) NOT NULL,
    phone character varying(20),
    specialization character varying(80) NOT NULL,
    zone_id integer,
    is_available boolean DEFAULT true NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: technicians_technician_id_seq; Type: SEQUENCE; Schema: smart_water; Owner: -
--

ALTER TABLE smart_water.technicians ALTER COLUMN technician_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME smart_water.technicians_technician_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: vw_daily_consumption; Type: VIEW; Schema: smart_water; Owner: -
--

CREATE VIEW smart_water.vw_daily_consumption AS
 WITH readings AS (
         SELECT meter_readings.meter_id,
            meter_readings.reading_time,
            meter_readings.cumulative_liters,
            lag(meter_readings.cumulative_liters) OVER (PARTITION BY meter_readings.meter_id ORDER BY meter_readings.reading_time) AS previous_liters,
            lag(meter_readings.reading_time) OVER (PARTITION BY meter_readings.meter_id ORDER BY meter_readings.reading_time) AS previous_time
           FROM smart_water.meter_readings
        )
 SELECT meter_id,
    (reading_time)::date AS reading_date,
    reading_time,
    (cumulative_liters - previous_liters) AS consumption_liters
   FROM readings
  WHERE ((previous_liters IS NOT NULL) AND (reading_time > previous_time) AND (cumulative_liters >= previous_liters));


--
-- Name: vw_leakage_detection; Type: VIEW; Schema: smart_water; Owner: -
--

CREATE VIEW smart_water.vw_leakage_detection AS
 WITH usage_history AS (
         SELECT vw_daily_consumption.meter_id,
            vw_daily_consumption.reading_date,
            vw_daily_consumption.consumption_liters,
            avg(vw_daily_consumption.consumption_liters) OVER (PARTITION BY vw_daily_consumption.meter_id ORDER BY vw_daily_consumption.reading_date ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS baseline_liters,
            count(*) OVER (PARTITION BY vw_daily_consumption.meter_id ORDER BY vw_daily_consumption.reading_date ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING) AS baseline_samples
           FROM smart_water.vw_daily_consumption
        )
 SELECT meter_id,
    reading_date,
    consumption_liters,
    round(baseline_liters, 2) AS baseline_liters,
        CASE
            WHEN ((baseline_samples >= 5) AND (baseline_liters > (0)::numeric) AND (consumption_liters > (baseline_liters * (2)::numeric))) THEN 'POSSIBLE_LEAK'::text
            ELSE 'NORMAL'::text
        END AS anomaly_status
   FROM usage_history;


--
-- Name: work_orders; Type: TABLE; Schema: smart_water; Owner: -
--

CREATE TABLE smart_water.work_orders (
    work_order_id bigint NOT NULL,
    incident_id bigint NOT NULL,
    technician_id bigint NOT NULL,
    status character varying(25) DEFAULT 'ASSIGNED'::character varying NOT NULL,
    repair_notes text,
    repair_cost numeric(12,2) DEFAULT 0 NOT NULL,
    assigned_at timestamp with time zone DEFAULT now() NOT NULL,
    completed_at timestamp with time zone,
    CONSTRAINT chk_repair_cost CHECK ((repair_cost >= (0)::numeric)),
    CONSTRAINT chk_work_order_status CHECK (((status)::text = ANY ((ARRAY['ASSIGNED'::character varying, 'IN_PROGRESS'::character varying, 'COMPLETED'::character varying, 'CANCELLED'::character varying])::text[])))
);


--
-- Name: work_orders_work_order_id_seq; Type: SEQUENCE; Schema: smart_water; Owner: -
--

ALTER TABLE smart_water.work_orders ALTER COLUMN work_order_id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME smart_water.work_orders_work_order_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: bill_audit audit_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_audit ALTER COLUMN audit_id SET DEFAULT nextval('public.bill_audit_audit_id_seq'::regclass);


--
-- Name: bills bill_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills ALTER COLUMN bill_id SET DEFAULT nextval('public.bills_bill_id_seq'::regclass);


--
-- Name: complaints complaint_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaints ALTER COLUMN complaint_id SET DEFAULT nextval('public.complaints_complaint_id_seq'::regclass);


--
-- Name: operators operator_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operators ALTER COLUMN operator_id SET DEFAULT nextval('public.operators_operator_id_seq'::regclass);


--
-- Name: payments payment_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments ALTER COLUMN payment_id SET DEFAULT nextval('public.payments_payment_id_seq'::regclass);


--
-- Name: residents resident_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.residents ALTER COLUMN resident_id SET DEFAULT nextval('public.residents_resident_id_seq'::regclass);


--
-- Name: roads road_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roads ALTER COLUMN road_id SET DEFAULT nextval('public.roads_road_id_seq'::regclass);


--
-- Name: water_connections connection_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.water_connections ALTER COLUMN connection_id SET DEFAULT nextval('public.water_connections_connection_id_seq'::regclass);


--
-- Name: water_knowledge knowledge_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.water_knowledge ALTER COLUMN knowledge_id SET DEFAULT nextval('public.water_knowledge_knowledge_id_seq'::regclass);


--
-- Name: zones zone_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones ALTER COLUMN zone_id SET DEFAULT nextval('public.zones_zone_id_seq'::regclass);


--
-- Name: bill_audit bill_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bill_audit
    ADD CONSTRAINT bill_audit_pkey PRIMARY KEY (audit_id);


--
-- Name: bills bills_connection_id_billing_month_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_connection_id_billing_month_key UNIQUE (connection_id, billing_month);


--
-- Name: bills bills_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_pkey PRIMARY KEY (bill_id);


--
-- Name: complaints complaints_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaints
    ADD CONSTRAINT complaints_pkey PRIMARY KEY (complaint_id);


--
-- Name: operators operators_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operators
    ADD CONSTRAINT operators_email_key UNIQUE (email);


--
-- Name: operators operators_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operators
    ADD CONSTRAINT operators_pkey PRIMARY KEY (operator_id);


--
-- Name: payments payments_bill_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_bill_id_key UNIQUE (bill_id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (payment_id);


--
-- Name: payments payments_transaction_reference_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_transaction_reference_key UNIQUE (transaction_reference);


--
-- Name: residents residents_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.residents
    ADD CONSTRAINT residents_email_key UNIQUE (email);


--
-- Name: residents residents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.residents
    ADD CONSTRAINT residents_pkey PRIMARY KEY (resident_id);


--
-- Name: review_assets review_assets_asset_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_assets
    ADD CONSTRAINT review_assets_asset_code_key UNIQUE (asset_code);


--
-- Name: review_assets review_assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_assets
    ADD CONSTRAINT review_assets_pkey PRIMARY KEY (asset_id);


--
-- Name: roads roads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roads
    ADD CONSTRAINT roads_pkey PRIMARY KEY (road_id);


--
-- Name: roads roads_zone_id_road_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roads
    ADD CONSTRAINT roads_zone_id_road_name_key UNIQUE (zone_id, road_name);


--
-- Name: water_connections water_connections_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.water_connections
    ADD CONSTRAINT water_connections_pkey PRIMARY KEY (connection_id);


--
-- Name: water_knowledge water_knowledge_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.water_knowledge
    ADD CONSTRAINT water_knowledge_pkey PRIMARY KEY (knowledge_id);


--
-- Name: zones zones_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_pkey PRIMARY KEY (zone_id);


--
-- Name: zones zones_zone_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.zones
    ADD CONSTRAINT zones_zone_name_key UNIQUE (zone_name);


--
-- Name: complaint_embeddings complaint_embeddings_pkey; Type: CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.complaint_embeddings
    ADD CONSTRAINT complaint_embeddings_pkey PRIMARY KEY (complaint_id);


--
-- Name: incident_embeddings incident_embeddings_pkey; Type: CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.incident_embeddings
    ADD CONSTRAINT incident_embeddings_pkey PRIMARY KEY (incident_id);


--
-- Name: incident_outbox incident_outbox_pkey; Type: CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.incident_outbox
    ADD CONSTRAINT incident_outbox_pkey PRIMARY KEY (event_id);


--
-- Name: incidents incidents_pkey; Type: CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.incidents
    ADD CONSTRAINT incidents_pkey PRIMARY KEY (incident_id);


--
-- Name: incidents incidents_source_event_id_key; Type: CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.incidents
    ADD CONSTRAINT incidents_source_event_id_key UNIQUE (source_event_id);


--
-- Name: meter_readings meter_readings_pkey; Type: CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.meter_readings
    ADD CONSTRAINT meter_readings_pkey PRIMARY KEY (reading_id);


--
-- Name: meters meters_meter_serial_key; Type: CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.meters
    ADD CONSTRAINT meters_meter_serial_key UNIQUE (meter_serial);


--
-- Name: meters meters_pkey; Type: CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.meters
    ADD CONSTRAINT meters_pkey PRIMARY KEY (meter_id);


--
-- Name: technicians technicians_pkey; Type: CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.technicians
    ADD CONSTRAINT technicians_pkey PRIMARY KEY (technician_id);


--
-- Name: meter_readings uq_meter_reading_time; Type: CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.meter_readings
    ADD CONSTRAINT uq_meter_reading_time UNIQUE (meter_id, reading_time);


--
-- Name: work_orders work_orders_pkey; Type: CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.work_orders
    ADD CONSTRAINT work_orders_pkey PRIMARY KEY (work_order_id);


--
-- Name: idx_bills_connection; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bills_connection ON public.bills USING btree (connection_id);


--
-- Name: idx_bills_connection_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bills_connection_month ON public.bills USING btree (connection_id, billing_month);


--
-- Name: idx_bills_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_bills_status ON public.bills USING btree (status);


--
-- Name: idx_complaints_resident; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_complaints_resident ON public.complaints USING btree (resident_id);


--
-- Name: idx_complaints_resident_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_complaints_resident_status ON public.complaints USING btree (resident_id, status);


--
-- Name: idx_connections_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_connections_status ON public.water_connections USING btree (status);


--
-- Name: idx_knowledge_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_knowledge_category ON public.water_knowledge USING btree (category);


--
-- Name: idx_knowledge_vector; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_knowledge_vector ON public.water_knowledge USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: ux_payments_bill_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ux_payments_bill_id ON public.payments USING btree (bill_id);


--
-- Name: idx_complaint_embedding_hnsw; Type: INDEX; Schema: smart_water; Owner: -
--

CREATE INDEX idx_complaint_embedding_hnsw ON smart_water.complaint_embeddings USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_incident_outbox_pending; Type: INDEX; Schema: smart_water; Owner: -
--

CREATE INDEX idx_incident_outbox_pending ON smart_water.incident_outbox USING btree (event_id) WHERE (delivered_at IS NULL);


--
-- Name: idx_incident_vector_hnsw; Type: INDEX; Schema: smart_water; Owner: -
--

CREATE INDEX idx_incident_vector_hnsw ON smart_water.incident_embeddings USING hnsw (embedding public.vector_cosine_ops);


--
-- Name: idx_incidents_zone_status; Type: INDEX; Schema: smart_water; Owner: -
--

CREATE INDEX idx_incidents_zone_status ON smart_water.incidents USING btree (zone_id, status);


--
-- Name: idx_meter_readings_time; Type: INDEX; Schema: smart_water; Owner: -
--

CREATE INDEX idx_meter_readings_time ON smart_water.meter_readings USING btree (meter_id, reading_time DESC);


--
-- Name: idx_one_active_meter_per_connection; Type: INDEX; Schema: smart_water; Owner: -
--

CREATE UNIQUE INDEX idx_one_active_meter_per_connection ON smart_water.meters USING btree (connection_id) WHERE ((meter_status)::text = 'ACTIVE'::text);


--
-- Name: idx_work_orders_technician; Type: INDEX; Schema: smart_water; Owner: -
--

CREATE INDEX idx_work_orders_technician ON smart_water.work_orders USING btree (technician_id, status);


--
-- Name: uq_active_incident_work_order; Type: INDEX; Schema: smart_water; Owner: -
--

CREATE UNIQUE INDEX uq_active_incident_work_order ON smart_water.work_orders USING btree (incident_id) WHERE ((status)::text = ANY ((ARRAY['ASSIGNED'::character varying, 'IN_PROGRESS'::character varying])::text[]));


--
-- Name: bills trg_bill_status_audit; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_bill_status_audit AFTER UPDATE OF status ON public.bills FOR EACH ROW EXECUTE FUNCTION public.audit_bill_status();


--
-- Name: bills trg_calculate_bill; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_calculate_bill BEFORE INSERT OR UPDATE OF units_consumed ON public.bills FOR EACH ROW EXECUTE FUNCTION public.set_bill_amount();


--
-- Name: incidents trg_incident_audit; Type: TRIGGER; Schema: smart_water; Owner: -
--

CREATE TRIGGER trg_incident_audit AFTER INSERT OR UPDATE OF status ON smart_water.incidents FOR EACH ROW EXECUTE FUNCTION smart_water.audit_incident_change();


--
-- Name: bills bills_connection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.bills
    ADD CONSTRAINT bills_connection_id_fkey FOREIGN KEY (connection_id) REFERENCES public.water_connections(connection_id);


--
-- Name: complaints complaints_connection_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaints
    ADD CONSTRAINT complaints_connection_id_fkey FOREIGN KEY (connection_id) REFERENCES public.water_connections(connection_id);


--
-- Name: complaints complaints_resident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.complaints
    ADD CONSTRAINT complaints_resident_id_fkey FOREIGN KEY (resident_id) REFERENCES public.residents(resident_id);


--
-- Name: operators operators_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.operators
    ADD CONSTRAINT operators_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(zone_id);


--
-- Name: payments payments_bill_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_bill_id_fkey FOREIGN KEY (bill_id) REFERENCES public.bills(bill_id);


--
-- Name: residents residents_road_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.residents
    ADD CONSTRAINT residents_road_id_fkey FOREIGN KEY (road_id) REFERENCES public.roads(road_id);


--
-- Name: review_assets review_assets_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.review_assets
    ADD CONSTRAINT review_assets_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(zone_id);


--
-- Name: roads roads_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.roads
    ADD CONSTRAINT roads_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(zone_id);


--
-- Name: water_connections water_connections_resident_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.water_connections
    ADD CONSTRAINT water_connections_resident_id_fkey FOREIGN KEY (resident_id) REFERENCES public.residents(resident_id);


--
-- Name: complaint_embeddings complaint_embeddings_complaint_id_fkey; Type: FK CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.complaint_embeddings
    ADD CONSTRAINT complaint_embeddings_complaint_id_fkey FOREIGN KEY (complaint_id) REFERENCES public.complaints(complaint_id) ON DELETE CASCADE;


--
-- Name: meters fk_smart_meter_connection; Type: FK CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.meters
    ADD CONSTRAINT fk_smart_meter_connection FOREIGN KEY (connection_id) REFERENCES public.water_connections(connection_id);


--
-- Name: incident_embeddings incident_embeddings_incident_id_fkey; Type: FK CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.incident_embeddings
    ADD CONSTRAINT incident_embeddings_incident_id_fkey FOREIGN KEY (incident_id) REFERENCES smart_water.incidents(incident_id) ON DELETE CASCADE;


--
-- Name: incident_outbox incident_outbox_incident_id_fkey; Type: FK CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.incident_outbox
    ADD CONSTRAINT incident_outbox_incident_id_fkey FOREIGN KEY (incident_id) REFERENCES smart_water.incidents(incident_id);


--
-- Name: incidents incidents_zone_id_fkey; Type: FK CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.incidents
    ADD CONSTRAINT incidents_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(zone_id);


--
-- Name: meter_readings meter_readings_meter_id_fkey; Type: FK CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.meter_readings
    ADD CONSTRAINT meter_readings_meter_id_fkey FOREIGN KEY (meter_id) REFERENCES smart_water.meters(meter_id);


--
-- Name: technicians technicians_zone_id_fkey; Type: FK CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.technicians
    ADD CONSTRAINT technicians_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zones(zone_id);


--
-- Name: work_orders work_orders_incident_id_fkey; Type: FK CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.work_orders
    ADD CONSTRAINT work_orders_incident_id_fkey FOREIGN KEY (incident_id) REFERENCES smart_water.incidents(incident_id);


--
-- Name: work_orders work_orders_technician_id_fkey; Type: FK CONSTRAINT; Schema: smart_water; Owner: -
--

ALTER TABLE ONLY smart_water.work_orders
    ADD CONSTRAINT work_orders_technician_id_fkey FOREIGN KEY (technician_id) REFERENCES smart_water.technicians(technician_id);


--
-- PostgreSQL database dump complete
--

\unrestrict ISh5UZncHMo72yY5IiY3UYL6AOUiqTnaj0qMSQloLAmV1WeO1qEGy1orqkBrNi8

