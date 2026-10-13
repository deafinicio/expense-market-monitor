import { search } from '@mradex77/google-play-scraper';
import { writeFileSync } from 'node:fs';
const locales = [
 ['en','us',['expense tracker','budget planner']],
 ['en','gb',['spending tracker','money manager']],
 ['uk','ua',['облік витрат','сімейний бюджет']],
 ['es','es',['control de gastos','presupuesto personal']],
 ['es','mx',['registro de gastos','control de gastos']],
 ['fr','fr',['suivi des dépenses','gestion budget']],
 ['de','de',['ausgaben tracker','haushaltsbuch']],
 ['pt','br',['controle de gastos','orçamento pessoal']],
 ['it','it',['gestione spese','bilancio familiare']],
 ['pl','pl',['kontrola wydatków','budżet domowy']],
 ['tr','tr',['harcama takibi','bütçe takip']],
 ['ja','jp',['家計簿','支出管理']],
 ['ko','kr',['가계부','지출 관리']],
 ['hi','in',['खर्च ट्रैकर','बजट प्लानर']],
 ['id','id',['catatan pengeluaran','pengatur anggaran']],
 ['ar','sa',['تتبع المصاريف','إدارة الميزانية']],
 ['zh','tw',['記帳','支出管理']],
];
const observations = {};
for(const [lang,country,queries] of locales){
 for(const query of queries){
  const key=[lang,country,query].join('|');
  try{
   const results=await search({term:query,lang,country,num:100});
   if(!Array.isArray(results))throw new Error('Non-array results');
   observations[key]={ok:true,apps:results.filter(x=>x.appId).map(x=>({
    id:String(x.appId),name:x.title||'',description:x.summary||'',
    url:'https://play.google.com/store/apps/details?id='+x.appId
   }))};
   console.log('GOOGLE',key,observations[key].apps.length);
  }catch(error){
   observations[key]={ok:false,error:String(error).slice(0,180)};
   console.error('GOOGLE FAILED',key,observations[key].error);
  }
  await new Promise(resolve=>setTimeout(resolve,500));
 }
}
writeFileSync('google_candidates.json',JSON.stringify(observations));
