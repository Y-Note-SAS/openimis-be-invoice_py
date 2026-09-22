from datetime import date

from invoice.models import Invoice, InvoicePayment, Bill, BillPayment, PaymentInvoice, DetailPaymentInvoice

DEFAULT_TEST_INVOICE_LINE_ITEM_PAYLOAD = {
    'code': 'LineItem1',
    'description': 'description_str',
    'details': {"test_int": 1, "test_txt": "some_str"},
    'ledger_account': 'account',
    'quantity': 10,
    'unit_price': 10.5,
    'discount': 15.5,
    'tax_rate': None,
    'tax_analysis': {'lines': [{'code': 'c', 'label': 'l', 'base': '0.1', 'amount': '2.00'}], 'total': '2.0'},
    'amount_net': 10 * 10.5 - 15.5,
    'amount_total': (10 * 10.5 - 15.5) + 2.0
}

DEFAULT_TEST_INVOICE_PAYLOAD = {
    'subject_type': 'contract',
    'subject_id': None,
    'thirdparty_type': 'insuree',
    'thirdparty_id': None,
    'code': 'INVOICE_CODE',
    'code_tp': 'INVOICE_CODE_TP',
    'code_ext': 'INVOICE_CODE_EXT',
    'date_due': date(2021, 9, 13),
    'date_invoice': date(2021, 9, 11),
    'date_payed': date(2021, 9, 12),
    'amount_discount': 20.1,
    'amount_net': 20.1,
    'tax_analysis': {'lines': [{'code': 'c', 'label': 'l', 'base': '0.1', 'amount': '2.01'}], 'total': '2.01'},
    'amount_total': 20.1,
    'status': Invoice.Status.VALIDATED,  # Validated
    'note': 'NOTE',
    'terms': 'TERMS',
    'payment_reference': 'payment reference'
}

DEFAULT_TEST_INVOICE_PAYMENT_PAYLOAD = {
    'label': 'label_pay',
    'code_tp': 'pay_sys_ref',
    'code_receipt': 'receipt number',
    'invoice': None,
    'amount_payed': '91.50',
    'fees': '12.00',
    'amount_received': '22.00',
    'date_payment': date(2021, 10, 10),
    'status': InvoicePayment.PaymentStatus.ACCEPTED
}

DEFAULT_TEST_BILL_PAYLOAD = {
    'subject_type': 'contract',
    'subject_id': None,
    'thirdparty_type': 'insuree',
    'thirdparty_id': None,
    'code': 'BILL_CODE',
    'code_tp': 'BILL_CODE_TP',
    'code_ext': 'BILL_CODE_EXT',
    'date_due': date(2021, 9, 13),
    'date_bill': date(2021, 9, 11),
    'date_payed': date(2021, 9, 12),
    'amount_discount': 20.1,
    'amount_net': 20.1,
    'tax_analysis': {'lines': [{'code': 'c', 'label': 'l', 'base': '0.1', 'amount': '2.01'}], 'total': '2.01'},
    'amount_total': 20.1,
    'status': Bill.Status.VALIDATED,  # Validated
    'note': 'NOTE',
    'terms': 'TERMS',
    'payment_reference': 'payment reference'
}

DEFAULT_TEST_BILL_PAYMENT_PAYLOAD = {
    'label': 'label_pay',
    'code_tp': 'pay_sys_ref',
    'code_receipt': 'receipt number',
    'bill': None,
    'amount_payed': 91.5,
    'fees': 12.0,
    'amount_received': 22.0,
    'date_payment': date(2021, 10, 10),
    'status': BillPayment.PaymentStatus.ACCEPTED
}

DEFAULT_TEST_BILL_LINE_ITEM_PAYLOAD = {
    'code': 'LineItem1',
    'description': 'description_str',
    'details': {"test_int": 1, "test_txt": "some_str"},
    'ledger_account': 'account',
    'quantity': 10,
    'unit_price': 10.5,
    'discount': 15.5,
    'tax_rate': None,
    'tax_analysis': {'lines': [{'code': 'c', 'label': 'l', 'base': '0.1', 'amount': '2.00'}], 'total': '2.0'},
    'amount_net': 10 * 10.5 - 15.5,
    'amount_total': (10 * 10.5 - 15.5) + 2.0
}

DEFAULT_TEST_PAYMENT_INVOICE_PAYLOAD = {
    'code_tp': 'PAY_CODE',
    'code_ext': 'PAY_CODE_EXT',
    'code_receipt': 'PAY_CODE_RCP',
    'label': 'test label',
    'reconciliation_status': PaymentInvoice.ReconciliationStatus.NOT_RECONCILIATED,
    'fees': 12.00,
    'amount_received': 91.50,
    'date_payment': date(2022, 4, 11),
    'payment_origin': 'payment origin',
    'payer_ref': 'payment reference',
    'payer_name': 'payer name'
}

DEFAULT_TEST_DETAIL_PAYMENT_INVOICE_PAYLOAD = {
    'payment_id': None,
    'subject_type': 'invoice',
    'subject_id': None,
    'status': DetailPaymentInvoice.DetailPaymentStatus.ACCEPTED,
    'fees': 12.00,
    'amount': 91.50,
    'reconcilation_id': 'RECONCID',
    'reconcilation_date': date(2022, 4, 11),
}
