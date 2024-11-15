from datetime import datetime

import pdfkit
from xml.etree import ElementTree as ET
from collections import defaultdict
import os
import unicodedata

from src.ShellPrinter import ShellPrinter


class PDFGenerator:
    def __init__(self, xml_file_path, output_dir):
        self.printer = ShellPrinter()
        self.xml_file_path = xml_file_path
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        current_date = datetime.now().strftime("%Y-%m-%d")
        self.output_pdf_path = os.path.join(self.output_dir, f"Journal_Entries_{current_date}.pdf")

    @staticmethod
    def normalize_text(text):
        """Normalize text to handle Unicode rendering."""
        return unicodedata.normalize("NFKD", text)

    def extract_entries_by_date(self):
        """Extract and organize journal entries by date from the XML file."""
        try:
            tree = ET.parse(self.xml_file_path)
            root = tree.getroot()
            data_section = root.find("Data")
            entries_by_date = defaultdict(list)
            date_key = None

            for element in data_section:
                if element.tag.startswith("date"):
                    date_key = element.text.strip()
                elif element.tag.startswith("entry") and date_key:
                    entries_by_date[date_key].append(self.normalize_text(element.text.strip()))
            return {date: "<br>".join(entries) for date, entries in entries_by_date.items()}
        except Exception as e:
            raise ValueError(f"Erreur lors de l'extraction des données XML : {e}")

    def generate_pdf(self):
        """
        Generate a PDF using PDFKit from enhanced HTML content.
        """
        entries_by_date = self.extract_entries_by_date()

        # Construire le contenu HTML avec styles CSS améliorés
        html_content = """
        <html>
        <head>
        <meta charset="utf-8">
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
            h1 { text-align: center; font-size: 24px; color: #333; margin-bottom: 20px; }
            .date { margin-top: 30px; font-weight: bold; font-size: 18px; color: #222; }
            .entry { margin-top: 10px; margin-bottom: 30px; text-indent: 20px; }
            hr { border: none; border-top: 1px solid #ccc; margin: 20px 0; }
            .footer { text-align: center; font-size: 12px; color: #888; position: fixed; bottom: 0; left: 0; right: 0; }
            @page { margin: 40px; }
        </style>
        </head>
        <body>
        <h1>Journal du Dovahkiin</h1>
        """

        # Ajout des entrées
        for date, text in entries_by_date.items():
            html_content += f"<div class='date'>Date: {date}</div>"
            html_content += f"<div class='entry'>{text}</div><hr>"

        # Ajouter un pied de page
        html_content += """
        <div class='footer'>
            Page <span class="pageNumber"></span> of <span class="totalPages"></span>
        </div>
        """

        html_content += "</body></html>"

        # Générer le PDF
        pdfkit.from_string(html_content, self.output_pdf_path, options={
            'footer-right': '[page] / [topage]',  # Numérotation des pages
            'footer-font-size': '10',
            'encoding': 'UTF-8'
        })

    def run(self):
        """Execute the process of extracting entries and generating the PDF."""
        try:
            self.generate_pdf()
            self.printer.success(f"PDF généré avec succés dans {self.output_pdf_path}")
        except Exception as e:
            self.printer.error(f"Problème de génération du PDF : {e}")
