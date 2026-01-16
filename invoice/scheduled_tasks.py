from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from policy.models import Policy
from dateutil.relativedelta import relativedelta
from invoice.models import Invoice
import datetime
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

def cron_correct_date_due():
    """
    Corrige les date_due erronées pour toutes les factures existantes.
    Règle : date_due doit être le payment_day du mois approprié
    """
    logger.info("Début de la correction des dates dues des factures...")
    print("Début de la correction des dates dues des factures...")

    all_invoices = Invoice.objects.filter(is_deleted=False)
    corrected_count = 0

    for invoice in all_invoices:
        # Récupérer les informations
        creation_date = invoice.date_created  # Date de création de la facture
        payment_day = invoice.date_due.day - 1     # Le jour de paiement

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
                            # Comparer avec la date To actuelle
                            logger.info(
                                "Comparaison facture %s: Ancienne dateto: %s et Nouvelle dateto: %s",
                                invoice.code,
                                invoice.date_valid_to.date(),
                                new_date_to
                            )
                            print(
                                "Comparaison facture %s: Ancienne dateto: %s et Nouvelle dateto: %s",
                                invoice.code,
                                invoice.date_valid_to.date(),
                                new_date_to
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
                                print("new_datetime %s", new_datetime)

                                invoice.date_valid_to = new_datetime
                                invoice.save(username="Admin", update_fields=['date_valid_to'])
                                corrected_count += 1
                            else:
                                print("Pas de mise a jour...")

    logger.info("Correction terminée. %s factures corrigées.", corrected_count)


def calculate_missing_months(last_invoice_date: py_date, periodicity: int, today: py_date) -> int:
    """
    Calcule le nombre de périodes manquées depuis la dernière facture.
    """
    # Date de la prochaine facture théorique
    next_due_date = last_invoice_date
    missing_periods = 0

    # Avancer jusqu'à dépasser aujourd'hui
    while next_due_date <= today:
        next_due_date = next_due_date + relativedelta(months=periodicity)
        if next_due_date <= today:
            missing_periods += 1

    return missing_periods


def calculate_due_date(today: py_date, payment_day: int, period: int) -> py_date:
    """
    Calcule la prochaine date d'échéance en tenant compte de la période.
    
    Args:
        today: Date actuelle
        payment_day: Jour de paiement souhaité (1-31)
        period: Période en mois
        (1=mensuel, 3=trimestriel, 6=semestriel, 12=annuel)
    
    Returns:
        Prochaine date d'échéance
    """
    # Si la période est > 1 mois, on ne compare pas avec today.day
    if period > 1:
        # Pour les périodes > 1 mois, on prend toujours le payment_day
        # du mois approprié selon la période

        # Calculer depuis une date de référence (première échéance)
        # Ici on suppose qu'on part de today, mais vous pourriez avoir
        # une date de début
        reference_date = today.replace(day=1) # Premier du mois comme référence

        # Trouver le prochain multiple de la période
        months_from_reference = 0
        temp_date = reference_date

        while temp_date <= today:
            temp_date = reference_date + relativedelta(
                months=months_from_reference)
            months_from_reference += period

        # Maintenant temp_date est la prochaine date de période
        year = temp_date.year
        month = temp_date.month

    else:
        # Période mensuelle (logique originale)
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

    # Ajuster le jour si nécessaire
    days_in_month = calendar.monthrange(year, month)[1]
    day = min(payment_day, days_in_month)

    return py_date(year, month, day)


def skipped_invoice_generation_script():
    """
    Rattrape les factures manquées.
    """
    today = py_datetime.today()
    logger.info("Début de la génération des factures manquées. Date: %s", today)
    print("Début de la génération des factures manquées. Date: %s", today)

    # Filtrer seulement les factures expirées
    expired_invoices = Invoice.objects.filter(
        is_deleted=False,
        date_valid_to__date__lt=today.date()
    )

    logger.warning("Factures expirées trouvées: %s", len(expired_invoices))
    print("Factures expirées trouvées: %s", len(expired_invoices))

    for invoice in expired_invoices:
        logger.info("Traitement facture: %s", invoice.code)

        if not invoice.subject_id:
            logger.warning("Facture %s sans subject_id, ignorée", invoice.code)
            continue

        # Vérifier la famille et la police
        try:
            family = Family.objects.get(
                validity_to__isnull=True,
                head_insuree=invoice.subject_id
            )
        except Family.DoesNotExist:
            logger.warning(
                "Famille non trouvée pour subject_id: %s", invoice.subject_id)
            continue

        try:
            insuree_policy = InsureePolicy.objects.get(
                validity_to__isnull=True,
                insuree_id=invoice.subject_id
            )
        except InsureePolicy.DoesNotExist:
            logger.warning("Police d'assuré non trouvée pour: %s", invoice.subject_id)
            continue

        policy = Policy.objects.filter(id=insuree_policy.policy_id).first()
        if not policy:
            logger.warning("Police non trouvée: %s", insuree_policy.policy_id)
            continue

        contribution = policy.contribution_plan
        if not contribution:
            logger.warning("Plan de contribution non trouvé pour police: %s", policy.id)
            continue

        # Vérifier la validité du plan de contribution
        if contribution.date_valid_from > today:
            logger.info("Plan de contribution non encore valide: %s", contribution.date_valid_from)
            continue

        if contribution.date_valid_to and contribution.date_valid_to <= today:
            logger.info("Plan de contribution expiré: %s", contribution.date_valid_to)
            continue

        # Déterminer la périodicité
        periodicity_map = {'M': 1, 'Q': 3, 'S': 6, 'Y': 12}
        periodicity = periodicity_map.get(policy.periodicity, 12)

        # Calculer le nombre de périodes manquées
        missing_periods = calculate_missing_months(
            invoice.date_valid_to.date(),
            periodicity,
            today.date()
        )
        print("**** %s nn %s nn %s", invoice.date_valid_to.date(), periodicity, today.date())

        if missing_periods == 0:
            logger.info("Aucune période manquée pour %s", invoice.code)
            print("Aucune période manquée pour %s", invoice.code)
            continue

        logger.info("Périodes manquées pour %s: %s", invoice.code, missing_periods)
        print("Périodes manquées pour %s: %s", invoice.code, missing_periods)

        # Récupérer le jour de paiement
        payment_day = int(policy.payment_day) if policy.payment_day else 5

        # Calculer les montants
        admin_user = InteractiveUser.objects.filter(id=1).first()
        if not admin_user:
            logger.error("Utilisateur admin non trouvé")
            continue

        # Calculer les montants (une seule fois)
        government_amount = Decimal('0')
        family_amount = Decimal('0')

        for calculation_rule in CALCULATION_RULES:
            # Montant gouvernement
            gov_result = calculation_rule.signal_calculate_event.send(
                sender=contribution.__class__.__name__,
                instance=contribution,
                user=admin_user,
                context="create",
                family=policy.family,
                is_government_value=True
            )
            if gov_result and gov_result[0][1]:
                government_amount = Decimal(str(gov_result[0][1]))

            # Montant famille
            fam_result = calculation_rule.signal_calculate_event.send(
                sender=contribution.__class__.__name__,
                instance=contribution,
                user=admin_user,
                context="create",
                family=policy.family,
                is_government_value=False
            )
            if fam_result and fam_result[0][1]:
                family_amount = Decimal(str(fam_result[0][1]))

        # Ajuster les montants selon la périodicité
        quantity = periodicity  # M=1, Q=3, S=6, Y=12
        government_amount_total = government_amount * quantity
        family_amount_total = family_amount * quantity

        # ID pour le code de facture
        chf_id = family.head_insuree.chf_id if family.head_insuree else str(family.id)

        # Date de base pour les calculs
        base_due_date = calculate_due_date(
            invoice.date_valid_to.date(), payment_day, periodicity)
        base_valid_to = base_due_date + relativedelta(months=periodicity) - timedelta(days=1)

        # Vérifier si des factures existent déjà pour ces dates
        existing_invoices = Invoice.objects.filter(
            subject_id=invoice.subject_id,
            date_valid_from__date__gte=base_due_date
        ).exists()

        if existing_invoices:
            logger.info("Factures existantes trouvées pour %s, ignoré", invoice.subject_id)
            continue

        # Créer les factures manquées
        for i in range(missing_periods):
            # Calculer les dates pour cette période
            period_due_date = base_due_date + relativedelta(months=periodicity * i)
            period_valid_from = period_due_date
            period_valid_to = base_valid_to + relativedelta(months=periodicity * i)

            # Générer un code unique
            timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
            base_code = f"{chf_id}{today.year}{today.month:02d}{today.day:02d}"

            # Créer facture gouvernement si montant > 0
            if government_amount_total > 0:
                gov_code = f"{base_code}-G-{timestamp}"
                create_invoice(
                    code=gov_code,
                    due_date=period_due_date,
                    valid_from=period_valid_from,
                    valid_to=period_valid_to,
                    amount=government_amount_total,
                    subject_id=family.head_insuree.id if family.head_insuree else None,
                    ledger_account="Etat",
                    quantity=quantity,
                    unit_price=government_amount,
                    admin_user=admin_user
                )

            # Créer facture famille si montant > 0
            if family_amount_total > 0:
                fam_code = f"{base_code}-F-{timestamp}"
                create_invoice(
                    code=fam_code,
                    due_date=period_due_date,
                    valid_from=period_valid_from,
                    valid_to=period_valid_to,
                    amount=family_amount_total,
                    subject_id=family.head_insuree.id if family.head_insuree else None,
                    ledger_account="Cotisant",
                    quantity=quantity,
                    unit_price=family_amount,
                    admin_user=admin_user
                )

    logger.info("Génération des factures manquées terminée")
    return True


def create_invoice(code, due_date, valid_from, valid_to, amount,
                   subject_id, ledger_account, quantity, unit_price, admin_user):
    """
    Crée une facture et sa ligne.
    """
    try:
        # Créer la facture
        invoice_service = InvoiceService(user=admin_user)
        invoice_values = {
            "code": code,
            "date_due": py_datetime.combine(due_date, py_datetime.min.time()),
            "date_valid_from": py_datetime.combine(valid_from, py_datetime.min.time()),
            "date_valid_to": py_datetime.combine(valid_to, py_datetime.min.time()),
            "amount_net": amount,
            "amount_total": amount,
            "status": 1,
            "cron_job_code": code,
            "subject_id": subject_id,
            "subject_type": "insuree",
            "thirdparty_id": subject_id,
            "thirdparty_type": "insuree"
        }

        logger.info("invoice_values %s", invoice_values)
        print("invoice_values %s", invoice_values)
        # invoice_result = invoice_service.create(invoice_values)

        if invoice_result.get("success"):
            # Créer la ligne de facture
            line_service = InvoiceLineItemService(user=admin_user)
            line_values = {
                "invoice_id": invoice_result["data"]["id"],
                "code": code,
                "ledger_account": ledger_account,
                "quantity": quantity,
                "unit_price": unit_price,
                "amount_net": amount,
                "amount_total": amount,
                "cron_job_code": code
            }

            line_result = line_service.create(line_values)
            logger.info("Facture créée: %s, Ligne: %s", code,
                        line_result.get('success', False)
                    )
            return True
        else:
            logger.error(
                "Erreur création facture %s: %s", code, invoice_result)
            return False

    except Exception as e:
        logger.error("Exception création facture %s: %s", code, str(e))
        return False


def invoice_generation_job():
    """
    Cette fonction cree les factures automatique en fontion des RFC
    """
    if InvoiceConfig.cron_auto_generate_invoices:
        today = py_datetime.today()
        all_invoices = Invoice.objects.filter(
            date_valid_to__date=today.date())
        logger.warning("All invoices found %s ", all_invoices)
        for invoice in all_invoices:
            print("invoice code ", invoice.code)
            logger.warning("subject_id %s ", invoice.subject_id)
            if not invoice.subject_id:
                logger.warning(
                    "No insuree found for invoice %s ", invoice.code)
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
                                                date_due = calculate_due_date(
                                                    today.date(), payment_day, periodicity)
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
    """
    This is the function to attach job to the system
    """
    scheduler.add_job(
        invoice_generation_job,
        # trigger=CronTrigger(day='4,9,14,19', hour=3, minute=0),
        trigger=CronTrigger(day='25,26', hour=3, minute=0),
        id="automatic_invoices_generation",
        max_instances=1,
        replace_existing=True,
        # misfire_grace_time=0 # Don't allow late executions
    )
