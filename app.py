import os
import pandas as pd
import smtplib
from databricks.sql import connect
from openai import OpenAI
from shiny import App, render, ui
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

DATBRICKS_API_KEY = os.getenv("DATABRICKS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
password = os.getenv("GMAIL_PASSWORD")
DATABRICKS_SERVER = os.getenv("DATABRICKS_SERVER")
DATABRICKS_HTTP_PATH = os.getenv("DATABRICKS_HTTP_PATH")


# Validate environment variables
if not all([DATBRICKS_API_KEY, DATABRICKS_SERVER, DATABRICKS_HTTP_PATH]):
    raise ValueError("❌ ERROR: Missing Databricks credentials in environment variables.")

if not OPENAI_API_KEY:
    raise ValueError("❌ ERROR: Missing OpenAI API Key in environment variables.")

 
# OpenAI Client
client = OpenAI(api_key=OPENAI_API_KEY)
model_id = "gpt-4o-mini-2024-07-18"
 
# System message for the assistant
system_message = """
Eres un asistente avanzado especializado en el análisis de datos. Recibirás un dataset de datos de proveedores.
Usa un número mínimo de tokens para resumir información clave y responder preguntas que haga el usuario sobre el dataset.
"""
 
 
# Function to query Databricks and return a DataFrame
def query_to_dataframe(query: str) -> pd.DataFrame:
    with connect(
        server_hostname=DATABRICKS_SERVER,
        http_path=DATABRICKS_HTTP_PATH,
        access_token=DATBRICKS_API_KEY,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]
 
    return pd.DataFrame(rows, columns=column_names)
 
 
# Fetch the forecasting data
query = "SELECT * FROM dbdemos.ia_demos.proveedores_productos_2"
df_forecasting_result = query_to_dataframe(query)


# Función para formatear datos en un mensaje para OpenAI
def create_user_message(input_text: str, df: pd.DataFrame) -> str:
    dataset_preview = df.to_string(index=False)
    return f"""
    Basado en el siguiente dataset, responde a la pregunta del usuario.
    
    Vista previa del dataset:
    {dataset_preview}
    
    Pregunta del usuario: {input_text}
    """

# Función para analizar el dataset con OpenAI
def analyze_dataset(input_text: str) -> str:
    input_message = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": create_user_message(input_text, df_forecasting_result)},
    ]

    response = client.chat.completions.create(
        model=model_id, messages=input_message, temperature=0, max_tokens=400
    )

    return response.choices[0].message.content.strip()


# Función para enviar correo usando SMTP con Gmail
def send_email():
    sender_email = "pypowerlabs@gmail.com"  # Correo del remitente (Gmail)
    receiver_email = "camilo.velez@bpt.com.co"  # Correo del destinatario
      # Usa una contraseña de aplicación de Gmail

    subject = "Orden de compra NO.19869"
    body = """
    Estimado Camilo Velez,
    
    Quisiéramos realizar un pedido de neumáticos. Por favor, confírmanos la disponibilidad y tiempos de entrega para 10 pares de neumáticos para camión.
    
    Muchas gracias.

    Saludos,
    Tu Empresa
    """

    # Crear el mensaje de correo
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, msg.as_string())
        server.quit()
        return "Correo enviado exitosamente a Camilo Vélez."
    except Exception as e:
        return f"Error al enviar el correo: {str(e)}"

# --- UI de Shiny ---
app_ui = ui.page_fluid(
    ui.h1("Análisis de proveedores y automátización de envío de correos con IA"),
    ui.panel_well(
        ui.h3("Consulta los datos con Agente de IA"),
        ui.input_text_area("user_input", "Haz una pregunta sobre los proveedores:", "", width="100%", height="100px"),
        ui.input_action_button("submit", "Obtener Respuesta"),
        ui.output_text_verbatim("response")
    ),
    ui.panel_well(
        ui.h3("Datos completos"),
        ui.output_data_frame("full_data")
    ),
    ui.panel_well(
        ui.h3("Enviar correo al mejor proveedor"),
        ui.input_action_button("send_email", "Enviar Pedido"),
        ui.output_text("email_status")
    )
)

# --- Servidor de Shiny ---
def server(input, output, session):
    @output
    @render.text
    def response():
        if input.submit() == 0:
            return "Ingresa una pregunta y haz clic en 'Obtener Respuesta'."
        return analyze_dataset(input.user_input())

    @output
    @render.data_frame
    def full_data():
        return df_forecasting_result

    @output
    @render.text
    def email_status():
        if input.send_email() > 0:
            return send_email()
        return "Presiona 'Enviar Pedido' para enviar el correo."

# Crear la aplicación Shiny
app = App(app_ui, server)
 