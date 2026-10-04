import json
import unittest
from custom_components.techem_portal.client import consumption, units, safe_url, TechemError, Document, Client
from unittest.mock import Mock

def page(obj):
    stream='1:'+json.dumps(obj)+'\n'
    # Exercise a record split across streamed script chunks.
    i=len(stream)//2
    return ''.join('<script>self.__next_f.push('+json.dumps([1,s])+')</script>' for s in (stream[:i],stream[i:]))

def data(amount=0,status='OK',period='2026-09'):
    return {'serviceType':'HEATING','consumption':{'service':'HEATING','period':period,'status':status,'unitOfMeasure':'KWH','amount':amount},'original':{'service':'HEATING','period':period,'status':'OK','unitOfMeasure':'HCU','amount':0},'averageConsumption':{'amount':204.408}}

class Tests(unittest.TestCase):
    def test_landing_ids_enriched_from_overview(self):
        client = Client()
        client.request = Mock(return_value=(page({'tenantDetails':[
            {'residentialUnitId':'UNIT-A','address':{'street':'Testweg 1','zip':'12345','city':'Teststadt','floor':'EGR'}},
            {'residentialUnitId':'UNIT-B','address':{'street':'Andere Wohnung'}}
        ]}), 'unused'))
        result = client.complete_addresses({'UNIT-A':{}})
        self.assertEqual(result['UNIT-A']['street'],'Testweg 1')
        self.assertEqual(result['UNIT-A']['floor'],'EGR')
        self.assertNotIn('UNIT-B',result)
        client.request.assert_called_once_with('https://mieter.techem.de/de/UNIT-A/consumptions')
    def test_address_wrong_unit_rejected(self):
        client = Client()
        client.request = Mock(return_value=(page({'tenantDetails':[{'residentialUnitId':'UNIT-B','address':{'floor':'EGR'}}]}), 'unused'))
        with self.assertRaises(TechemError):client.complete_addresses({'UNIT-A':{}})
    def test_zero_is_valid(self):self.assertEqual(consumption(page(data()),'2026-09')['heating_kwh'],0)
    def test_decimal_not_comparison(self):self.assertEqual(consumption(page(data(12.34)),'2026-09')['heating_kwh'],12.34)
    def test_missing_and_invalid(self):
        for amount in (None,True,'0',-1,float('nan'),float('inf')):
            with self.subTest(amount=amount),self.assertRaises(TechemError):consumption(page(data(amount)),'2026-09')
    def test_wrong_month(self):
        with self.assertRaises(TechemError):consumption(page(data()),'2026-08')
    def test_bad_status(self):
        with self.assertRaises(TechemError):consumption(page(data(status='MISSING')),'2026-09')
    def test_login_page(self):
        with self.assertRaises(TechemError):consumption('<html>Anmelden</html>','2026-09')
    def test_conflicting_values(self):
        with self.assertRaises(TechemError):consumption(page([data(1),data(2)]),'2026-09')
    def test_unit_mismatch(self):
        with self.assertRaises(TechemError):consumption(page(data()),'2026-09','OTHER')
    def test_two_addresses(self):
        html=page({'tenantDetails':[{'residentialUnitId':'UNIT-A','address':{'street':'Testweg 1','zip':'12345','city':'Teststadt','floor':'EGR'}},{'residentialUnitId':'UNIT-B','address':{'floor':'2OG'}}]})
        self.assertEqual(units(html)['UNIT-A']['floor'],'EGR')
        self.assertEqual(len(units(html)),2)
    def test_redirect_restrictions(self):
        for url in ('http://mieter.techem.de','https://evil.example','https://mieter.techem.de.evil.example','https://mieter.techem.de@evil.example'):
            with self.subTest(url=url),self.assertRaises(TechemError):safe_url(url)
    def test_callback_form(self):
        form=Document('<form method="post" action="https://mieter.techem.de/api/auth/callback/azure-b2c"><input name="state" value="a&amp;b"></form>').forms[0]
        self.assertEqual(form['fields']['state'],'a&b')

if __name__=='__main__':unittest.main()
