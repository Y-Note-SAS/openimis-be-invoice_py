from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from policy.models import Policy
from invoice.models import Invoice
from datetime import timedelta, datetime as py_datetime, date as py_date
import calendar
from insuree.models import InsureePolicy, Family, Insuree
from policy.models import Policy
import logging
from core.datetimes.shared import datetimedelta
from core.models import InteractiveUser
from decimal import Decimal
from policy.apps import CALCULATION_RULES
from invoice.services import InvoiceService
from invoice.services.invoiceLineItem import InvoiceLineItemService
from invoice.apps import InvoiceConfig

logger = logging.getLogger(__name__)

def cron_correct_amount():
    """
    Corrige les date_due erronées pour toutes les factures existantes.
    Règle : date_due doit être le payment_day du mois approprié
    """
    logger.info("Début de la correction des dates dues des factures...")

    all_invoices = Invoice.objects.filter(is_deleted=False)
    corrected_count = 0

    for invoice in all_invoices:
        # Récupérer les informations
        creation_date = invoice.date_created  # Date de création de la facture
        print("type ", type(creation_date))
        print("type invoice.date_valid_to ", type(invoice.date_valid_to))
        payment_day = invoice.date_valid_to.day     # Le jour de paiement

        # Calculer la date_due correcte
        if payment_day < creation_date.day:
            # Mois suivant
            if creation_date.month == 12:
                year = creation_date.year + 1
                month = 1
            else:
                year = creation_date.year
                month = creation_date.month + 1
        else:
            # Mois courant
            year = creation_date.year
            month = creation_date.month

        # Vérifier si le jour existe dans ce mois
        days_in_month = calendar.monthrange(year, month)[1]

        if payment_day > days_in_month:
            # Le jour n'existe pas dans ce mois
            # prendre le dernier jour du mois
            day = days_in_month
        else:
            day = payment_day
        correct_due_date = py_date(year, month, day)

        # Tout ce block c'est juste pour récupérer la périodicité afin de
        # recalculer la date_to
        if invoice.subject_id:
            family = Family.objects.filter(
                validity_to__isnull=True,
                head_insuree=invoice.subject_id).first()
            if family:
                insureepolicy = InsureePolicy.objects.filter(
                    validity_to__isnull=True,
                    insuree_id=invoice.subject_id).first()
                if insureepolicy:
                    policy_id = insureepolicy.policy_id
                    if policy_id:
                        policy = Policy.objects.filter(id=policy_id).first()
                        if policy:
                            periodicity = 12
                            if policy.periodicity:
                                if policy.periodicity == 'Q':
                                    periodicity = 3
                                elif policy.periodicity == 'S':
                                    periodicity = 6
                                elif policy.periodicity == 'M':
                                    periodicity = 1
                            # Périodicité retrouvée
                            logger.info("periodicity %s", periodicity)
                            new_date_to = correct_due_date + datetimedelta(
                                months=periodicity
                            )
                            # Comparer avec la date_due actuelle
                            logger.info(
                                "Comparaison facture %s: Ancienne date_due: %s et Nouvelle date_due: %s",
                                invoice.code,
                                invoice.date_valid_to.date(),
                                correct_due_date
                            )
                            if invoice.date_valid_to.date() != new_date_to:
                                logger.info("Mise a jour*")
                                # Mettre à jour la date_due
                                # Garder l'heure/minute/seconde d'origine,
                                # changer seulement la date
                                old_datetime = invoice.date_valid_to
                                new_datetime = py_datetime.combine(
                                    new_date_to,
                                    old_datetime.time(),
                                    tzinfo=old_datetime.tzinfo
                                )
                                logger.info("new_datetime %s", new_datetime)

                                invoice.date_valid_to = new_datetime
                                # invoice.save(update_fields=['date_to'])
                                corrected_count += 1
                            else:
                                print("Pas de mise a jour...")

    logger.info("Correction terminée. %s factures corrigées.", corrected_count)


def invoice_generation_job():
    """
    Cette fonction cree les factures automatique en fontion des RFC
    """
    print("Crontab for invoices generation started...")
    if InvoiceConfig.cron_auto_generate_invoices:
        today = py_datetime.today()
        all_invoices = Invoice.objects.filter(
            date_valid_to__date=today.date())
        logger.warning("All invoices found %s ", all_invoices)
        for invoice in all_invoices:
            print("invoice code ", invoice.code)
            logger.warning("subject_id %s ", invoice.subject_id)
            if not invoice.subject_id:
                logger.warning("No insuree found for invoice %s ", invoice.code)
            if invoice.subject_id:
                family = Family.objects.filter(
                    validity_to__isnull=True,
                    head_insuree=invoice.subject_id).first()
                logger.warning("family %s ", family)
                if family:
                    insureepolicy = InsureePolicy.objects.filter(
                        validity_to__isnull=True,
                        insuree_id=invoice.subject_id).first()
                    if not insureepolicy:
                        logger.warning("No insureepolicy for insuree %s ", invoice.subject_id)
                    if insureepolicy:
                        policy_id = insureepolicy.policy_id
                        if policy_id:
                            policy = Policy.objects.filter(id=policy_id).first()
                            if not policy:
                                logger.warning("No insuree policy for insureepolicy %s ", insureepolicy)
                            if policy:
                                contribution = policy.contribution_plan
                                if not contribution:
                                    logger.warning("No contribution inside policy  %s ", policy)
                                if contribution:
                                    generate = False
                                    logger.warning("contribution date_valid_from  %s ", contribution.date_valid_from)
                                    if today > contribution.date_valid_from:
                                        if contribution.date_valid_to:
                                            if contribution.date_valid_to > today:
                                                generate = True
                                        else:
                                            # Validity to is null
                                            generate = True
                                    logger.warning("generate ? %s ", generate)
                                    if generate:
                                        periodicity = 12
                                        if policy.periodicity:
                                            if policy.periodicity == 'Q':
                                                periodicity = 3
                                            elif policy.periodicity == 'S':
                                                periodicity = 6
                                            elif policy.periodicity == 'M':
                                                periodicity = 1
                                        renewal_date = today + datetimedelta(
                                            months=periodicity
                                        )
                                        logger.warning("renewal date %s", renewal_date)
                                        renewal_date = today + datetimedelta(
                                            months=periodicity
                                        )
                                        logger.warning("renewal date %s", renewal_date)
                                        ok = False
                                        if not contribution.date_valid_to:
                                            ok = True
                                        else:
                                            if renewal_date < contribution.date_valid_to:
                                                ok = True
                                        logger.warning("Is OK ? %s ", ok)
                                        if ok:
                                            family_amount = 0
                                            government_amount = 0
                                            for calculation_rule in CALCULATION_RULES:
                                                # get calculation_rule amount for government
                                                admin_user = InteractiveUser.objects.filter(
                                                    id=1).first()
                                                logger.warning("admin_user %s ", admin_user)
                                                result_signal = calculation_rule.signal_calculate_event.send(
                                                    sender=contribution.__class__.__name__, instance=contribution,
                                                    user=admin_user, context="create",
                                                    family=policy.family,
                                                    is_government_value=True
                                                )
                                                logger.warning("result_signal %s ", result_signal)
                                                if result_signal[0][1]:
                                                    government_amount = Decimal(result_signal[0][1])
                                                    logger.warning("government_amount %s ", government_amount)
                                                
                                                # get calculation_rule for familly
                                                result_signal = calculation_rule.signal_calculate_event.send(
                                                    sender=contribution.__class__.__name__, instance=contribution,
                                                    user=admin_user, context="create",
                                                    family=policy.family,
                                                    is_government_value=False
                                                )
                                                logger.warning("result_signal2 %s ", result_signal)
                                                if result_signal[0][1]:
                                                    family_amount = Decimal(result_signal[0][1])
                                                    logger.warning("family_amount %s ", family_amount)
                                                if family.head_insuree:
                                                    chf_id = family.head_insuree.chf_id
                                                else:
                                                    chf_id = family.id
                                                code = (chf_id) + str(today.year) + str(today.month)
                                                code += "-" + str(py_datetime.now())
                                                payment_day = 5 #5 par défaut
                                                if policy.payment_day:
                                                    payment_day = int(policy.payment_day)
                                                # Déterminer l'année et le mois
                                                if payment_day < today.day:
                                                    # Mois suivant
                                                    if today.month == 12:
                                                        year = today.year + 1
                                                        month = 1
                                                    else:
                                                        year = today.year
                                                        month = today.month + 1
                                                else:
                                                    # Mois courant
                                                    year = today.year
                                                    month = today.month

                                                # Vérifier si le jour existe dans ce mois
                                                days_in_month = calendar.monthrange(year, month)[1]

                                                if payment_day > days_in_month:
                                                    # Le jour n'existe pas dans ce mois
                                                    # prendre le dernier jour du mois
                                                    day = days_in_month
                                                else:
                                                    day = payment_day
                                                date_due = py_date(year, month, day)
                                                logger.warning("date due %s", date_due)
                                                if policy.payment_day:
                                                    date_due = date_due.replace(day=int(policy.payment_day))
                                                    logger.warning("date due updated %s", date_due)
                                                date_to = date_due + datetimedelta(
                                                    months=periodicity
                                                )
                                                date_valid_to = date_to - timedelta(days=1)
                                                logger.warning("current date_valid_to %s", date_valid_to)
                                                existing_invoices = Invoice.objects.filter(
                                                    subject_id=invoice.subject_id,
                                                    date_valid_from__date__gte=date_due.date()
                                                )
                                                logger.warning("existing_invoices %s", existing_invoices)
                                                if not existing_invoices:
                                                    quantity = 1
                                                    if policy.periodicity:
                                                        if policy.periodicity == 'Q':
                                                            family_amount = family_amount * 3
                                                            quantity = 3
                                                            government_amount = government_amount * 3
                                                        elif policy.periodicity == 'S':
                                                            family_amount = family_amount * 6
                                                            quantity = 6
                                                            government_amount = government_amount * 6
                                                        elif policy.periodicity == 'Y':
                                                            family_amount = family_amount * 12
                                                            quantity = 12
                                                            government_amount = government_amount * 12
                                                    logger.warning("government amount %s ",
                                                                    government_amount)
                                                    logger.warning("family amount %s ", family_amount)
                                                    logger.warning("head insuree %s ",
                                                        policy.family.head_insuree)
                                                    # create goverment invoice
                                                    if government_amount > 0:
                                                        values = {
                                                            "code": code,
                                                            "date_due": date_due,
                                                            "date_valid_from": date_due,
                                                            "date_valid_to": date_valid_to,
                                                            "amount_net": government_amount,
                                                            "amount_total": government_amount,
                                                            "status": 1,
                                                            "cron_job_code": code
                                                        }
                                                        if policy.family.head_insuree:
                                                            values["subject_id"] = family.head_insuree.id
                                                            values["subject_type"] = "insuree"
                                                            values["thirdparty_id"] = family.head_insuree.id
                                                            values["thirdparty_type"] = "insuree"
                                                            if family_amount > 0:
                                                                # update code as two invoice will be
                                                                # created as the code is unique
                                                                values["code"] = values["code"] + "-G"
                                                        invoice_service = InvoiceService(user=admin_user)
                                                        result_invoice = invoice_service.create(
                                                            values
                                                        )
                                                        logger.warning(
                                                            "Invoice government_amount created %s",
                                                            result_invoice)
                                                        print("Invoice government_amount created ",
                                                            result_invoice)
                                                        if result_invoice["success"] is True:
                                                            invoice_line_item_service =\
                                                                InvoiceLineItemService(user=admin_user)
                                                            item_values = {
                                                                "invoice_id": result_invoice["data"]["id"],
                                                                "code": code,
                                                                "ledger_account": "Etat",
                                                                "quantity": quantity,
                                                                "unit_price": government_amount,
                                                                "amount_net": government_amount,
                                                                "amount_total": government_amount,
                                                                "cron_job_code": code
                                                            }
                                                            if family_amount > 0:
                                                                # update code as two invoice will be
                                                                # created as the code is unique
                                                                item_values["code"] = item_values["code"] + "-G" +\
                                                                str(py_datetime.now())
                                                            result = invoice_line_item_service.create(
                                                                item_values
                                                            )
                                                            logger.warning(
                                                                "Invoice line gov_amount created %s",
                                                                result)
                                                    # create Family invoice
                                                    if family_amount > 0:
                                                        invoice_service = InvoiceService(user=admin_user)
                                                        gov_values = {
                                                            "code": code,
                                                            "date_due": date_due,
                                                            "date_valid_from": date_due,
                                                            "date_valid_to": date_valid_to,
                                                            "amount_net": family_amount,
                                                            "amount_total": family_amount,
                                                            "status": 1,
                                                            "cron_job_code": code
                                                        }
                                                        if policy.family.head_insuree:
                                                            gov_values["subject_id"] = policy.\
                                                                family.head_insuree.id
                                                            gov_values["subject_type"] = "insuree"
                                                            gov_values["thirdparty_id"] = policy.\
                                                                family.head_insuree.id
                                                            gov_values["thirdparty_type"] = "insuree"
                                                        result_invoice = invoice_service.create(
                                                            gov_values
                                                        )
                                                        logger.warning(
                                                            "Invoice family amount created %s",
                                                            result_invoice)
                                                        if result_invoice["success"] is True:
                                                            invoice_line_item_service =\
                                                                InvoiceLineItemService(user=admin_user)
                                                            result = invoice_line_item_service.create(
                                                                {
                                                                    "invoice_id": result_invoice["data"]["id"],
                                                                    "code": code,
                                                                    "ledger_account": "Cotisant",
                                                                    "quantity": quantity,
                                                                    "unit_price": family_amount,
                                                                    "amount_net": family_amount,
                                                                    "amount_total": family_amount,
                                                                    "cron_job_code": code
                                                                }
                                                            )
                                                            logger.warning(
                                                                "Invoice line amount_family created %s",
                                                                result)
    logger.warning("Crontab for invoices generation finished...")
    return True

def schedule_tasks(scheduler: BackgroundScheduler):
    scheduler.add_job(
        invoice_generation_job,
        trigger=CronTrigger(day='5,10,15,20', hour=3, minute=0),
        id="automatic_invoices_generation",
        max_instances=1,
        replace_existing=True,
        # misfire_grace_time=0 # Don't allow late executions
    )