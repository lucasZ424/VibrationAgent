# Vibration Agent Design

Source: `Agent/vibration_agent_design.docx`
Generated for Codex-readable project context. Keep the DOCX as the human design source if both diverge.

# 鎸姩瀛﹀涔犲姪鎵嬭璁℃枃妗ｏ紙瀹屾暣鐗堬紝鍚妧鏈爤 / 鐭ヨ瘑搴?/ Skills / 绀轰緥锛?

> 鐢ㄩ€旓細鑷敤銆侀暱鏈熻凯浠ｃ€佸伐绋嬪鍚戠殑鎸姩瀛︿笓绮惧涔犱笌鐮旂┒鍔╂墜

> 鏈枃妗ｆ暣鍚堝墠涓夋璁ㄨ涓殑瀹屾暣璁捐寤鸿锛岀洰鏍囨槸鎻愪緵涓€浠戒俊鎭瘑搴﹂珮銆佷究浜庡悗缁氦鍙夐獙璇佸拰瀹為檯寮€鍙戠殑鎬昏璁＄銆傛枃妗ｉ粯璁ら噰鐢ㄦ垜璁や负鏈€鍚堢悊鐨勬柟妗堬紝闄ら潪浣犱箣鍓嶅凡缁忔槑纭ˉ鍏呮垨璁㈡銆傚畠涓嶆槸闈㈠悜澶栭儴鍥㈤槦鐨勬寮?PRD锛岃€屾槸闈㈠悜浣犺嚜宸卞悗缁疄鐜般€佹牎楠屻€佽鍓拰鎵╁睍鐨勬妧鏈摑鍥俱€傛牳蹇冨師鍒欏彧鏈変竴鏉★細杩欎釜绯荤粺蹇呴』鏄庢樉浼樹簬鈥滄妸鏂囨。鐩存帴鎵旂粰閫氱敤妯″瀷闂瓟鈥濈殑鍋氭硶锛屽惁鍒欐病鏈夋惌寤轰笓鐢?agent 鐨勬剰涔夈€?

## 0. 鍒濇湡闇€姹傞噸瀹氫箟锛圲RGENT锛?

褰撳墠闃舵鐨勯瑕佺洰鏍囦笉鏄竴娆℃€у畬鎴愬畬鏁翠笓涓氱増锛岃€屾槸灏藉揩钀藉湴涓€涓煭鏈熷彲鐢ㄧ殑鎸姩瀛︾煡璇嗗簱 Agent銆傝繖涓鏈熺増鏈繀椤昏兘璇诲彇鐭ヨ瘑搴撴枃浠躲€佹彁鍙栨枃瀛楀唴瀹广€佸仛鍩虹娓呮礂涓庡垏鍒嗐€佺敓鎴愭憳瑕佹垨绔犺妭鎬荤粨锛屽苟鍩轰簬宸插叆搴撳唴瀹瑰畬鎴愰棶绛斻€?

瀹炵幇褰㈡€佷互鈥淟LM 鎸?tools + 绠€鍗?skills鈥?涓轰富锛屽己璋冨厛鎶婁富閾捐矾璺戦€氾紝鍐嶉€愭琛ヨ瘉鎹牳楠屻€佸妯″瀷鍗忎綔銆乼axonomy 涓庡鏉傚伐绋嬭兘鍔涖€傞鏈熶氦浠樻爣鍑嗗簲浠モ€滃彲鐢ㄣ€佸彲鏌ャ€佸彲缁х画杩唬鈥濅负绗竴鐩爣锛岃€屼笉鏄拷姹傚畬鏁寸増璁捐涓€娆″埌浣嶃€?

- URGENT锛氱煡璇嗗簱鏂囦欢鏂囧瓧鎻愬彇涓庡熀纭€娓呮礂锛屼紭鍏堣鐩?PDF銆佹壂鎻?PDF銆丮arkdown銆乀XT銆丏OCX 绛夊父瑙佽祫鏂欍€?
- URGENT锛氬熀纭€ chunking銆佹渶灏忕储寮曚笌妫€绱㈣兘鍔涳紝淇濊瘉宸插叆搴撳唴瀹硅兘琚ǔ瀹氬彫鍥炵敤浜庢€荤粨涓庨棶绛斻€?
- URGENT锛氭€荤粨涓庨棶绛旇兘鍔涳紝鑷冲皯鏀寔鏁寸瘒鎽樿銆佺珷鑺傛憳瑕併€侀拡瀵圭煡璇嗗簱鍐呭鐨勫畾鍚戞彁闂€?
- URGENT锛氱粺涓€鍏ュ彛 Agent 缂栨帓锛岄噰鐢ㄥ皯閲忕畝鍗?skills 杩炴帴鎽勫彇銆佹绱€佹€荤粨涓庨棶绛斻€?
浠ヤ笅鑳藉姏淇濈暀鍦ㄨ璁′腑锛屼絾涓嶅簲闃诲棣栨湡锛氬畬鏁村妯″瀷瀹＄閾俱€佸畬鍠?taxonomy 娌夋穩銆佺爺绌舵绱㈠寮恒€佹ā鍨嬮€夋嫨涓庡疄楠屾祴閲忓缓璁€佸叏闈㈣瘉鎹爣绛句綋绯汇€?

## 1. 鐩爣銆佽竟鐣屼笌璁捐鍩虹嚎锛圲RGENT锛?

绯荤粺鐨勬渶缁堢洰鏍囦笉鏄仛涓€涓硾鍖栬亰澶╂満鍣ㄤ汉锛岃€屾槸鍋氫竴涓€滄尟鍔ㄥ浼樺厛銆佸伐绋嬮」鐩紭鍏堛€佽瘉鎹紭鍏堚€濈殑涓汉宸ヤ綔鍙般€傚畠鐨勪富瑕佷娇鐢ㄥ満鏅笉鏄€冭瘯棰樺拰鏍囧噯璇惧悗棰橈紝鑰屾槸瀹為檯宸ョ▼椤圭洰涓亣鍒扮殑姒傚康鐞嗚В銆佹ā鍨嬮€夋嫨銆佸弬鏁版剰涔夎鲸鏋愩€佸叕寮忛€傜敤鑼冨洿鍒ゆ柇銆佹枃妗ｆ潯鏂囧畾浣嶃€佺浉鍏宠鏂囪皟鐮斻€佸凡鏈夎В鍐宠矾寰勬€荤粨锛屼互鍙婃妸鐞嗚鐭ヨ瘑杞寲涓哄伐绋嬭В閲婂拰涓嬩竴姝ヨ鍔ㄥ缓璁€備綘褰撳墠澶勪簬瀛︿範闃舵锛屼絾瀛︿範鐨勭洰鏍囨槸鏈嶅姟鐪熷疄椤圭洰锛屽洜姝ょ郴缁熷繀椤婚粯璁ら噰鐢ㄥ伐绋嬫ā寮忚緭鍑猴紝鑰屼笉鏄鏍¤€冭瘯绛旀妯″紡銆?

杩欎竴瀹氫箟鐩存帴鍐冲畾浜嗙郴缁熺殑杈圭晫锛氱涓€锛屽畠涓嶈兘涓昏渚濊禆涓绘ā鍨嬫湰韬殑娉涘寲甯歌瘑锛屽繀椤诲敖閲忎緷璧栨湰鍦扮煡璇嗗簱銆佺粨鏋勫寲鏂囨。鍜屽彲鏍搁獙鐨勮瘉鎹€傜浜岋紝瀹冧笉鑳芥妸鈥滅浉鍏冲唴瀹瑰彫鍥炲埌浜嗏€濊褰撴垚鈥滃凡缁忔湁浜嗛珮璐ㄩ噺绛旀鈥濓紱瀹冨繀椤诲绗﹀彿銆佸崟浣嶃€佷笂涓嬫枃璇箟鍜屾潵婧愮瓑绾у仛杩涗竴姝ュ鐞嗐€傜涓夛紝瀹冧笉鑳戒互鐢熸垚娴佺晠绛旀涓轰富瑕佹垚鍔熸爣鍑嗭紝鑰岃浠モ€滄槸鍚︿笓绮俱€佹槸鍚︾ǔ銆佹槸鍚﹀彲杩芥函銆佹槸鍚﹁兘鍦ㄥ伐绋嬩笂浣跨敤鈥濅负鎴愬姛鏍囧噯銆?

## 2. 鎬讳綋缁撹锛氭槸鍚﹂€傚悎鐢变竴涓?agent 闆嗕腑瀹屾垚锛圲RGENT锛?

缁撹鏄細閫傚悎鐢变竴涓粺涓€鍏ュ彛鐨?agent 瀵瑰瀹屾垚锛屼絾缁濅笉閫傚悎鐢变竴涓崟浣撳ぇ妯″瀷銆佸崟鎻愮ず璇嶃€佸崟閾捐矾鏉ュ畬鎴愩€傛渶鍚堢悊鐨勫舰寮忔槸鈥滀竴涓€绘帶 Tutor-Orchestrator + 澶氫釜涓撲笟 skills + 鏈湴鐭ヨ瘑搴?/ 娣峰悎妫€绱㈠眰 + 澶氭ā鍨嬪绋夸笌鏍搁獙灞傗€濄€備粠鐢ㄦ埛瑙嗚鐪嬶紝瀹冧粛鐒舵槸涓€涓涔犲姪鎵嬶紱浠庣郴缁熻瑙掔湅锛屽畠鏄竴涓湁涓ユ牸璺敱鍜岃竟鐣屾帶鍒剁殑棰嗗煙绯荤粺銆?

杩欎箞鍋氱殑鍘熷洜鍦ㄤ簬锛屼綘鎻愬嚭鐨勫洓绫绘牳蹇冮渶姹傗€斺€旀枃妗ｉ槄璇绘€荤粨銆佺簿鍑嗛棶绛斻€佸寮烘悳绱笌鐭ヨ瘑搴撱€佺爺绌惰緟鍔┾€斺€斿湪宸ョ▼涓婂垎鍒睘浜庢枃妗ｈВ鏋愩€佹绱㈠寮洪棶绛斻€佺煡璇嗙鐞嗐€佸閮ㄧ爺绌舵绱㈠洓鏉′笉鍚屼换鍔￠摼銆傚畠浠殑杈撳叆绫诲瀷銆佸け璐ユā寮忋€佸鏃跺欢鍜屽噯纭巼鐨勮姹傞兘涓嶅悓銆傚鏋滅矖鏆村湴濉炶繘涓€涓?agent prompt 閲岋紝绯荤粺浼氬緢蹇€€鍖栨垚鈥滈€氱敤妯″瀷 + 宸ュ叿璋冪敤鈥濈殑鏉炬暎缁勫悎锛屾棤娉曞舰鎴愮湡姝ｇ殑涓撶簿浼樺娍銆?

瀵瑰簲褰撳墠闃舵鐨勬敹缂╃増瀹炵幇锛屽彲鍏堟妸缁熶竴鍏ュ彛鍘嬬缉涓衡€滀竴涓富鎺?LLM + tools + 灏戦噺绠€鍗?skills鈥濓紝浼樺厛淇濈暀鏂囨。鎽勫彇涓庤В鏋愩€佺煡璇嗗簱妫€绱€佹€荤粨/闂瓟涓夋潯涓婚摼璺紝鍏朵綑鑳藉姏鍏堜綔涓哄悗缁墿灞曟帴鍙ｄ繚鐣欍€?

## 3. 鎬讳綋鏋舵瀯锛堟渶浣虫帹鑽愭柟妗堬級锛圲RGENT锛?

鎺ㄨ崘閲囩敤浜斿眰鏋舵瀯锛氫氦浜掑眰銆佷换鍔″眰銆佽川閲忔帶鍒跺眰銆佺煡璇嗗眰銆佹暟鎹眰銆備氦浜掑眰鍙湁涓€涓粺涓€鍏ュ彛锛屽嵆 Tutor-Orchestrator锛岃礋璐ｈ瘑鍒剰鍥俱€佸喅瀹氳矾鐢便€佹眹鎬荤粨鏋溿€佹帶鍒舵渶缁堣緭鍑洪鏍笺€備换鍔″眰鐢卞涓?skills 缁勬垚锛屾瘡涓?skill 鍙礋璐ｄ竴绉嶄换鍔★紝涓嶅厑璁稿悓鏃跺吋椤炬绱€佹帹瀵笺€佹€荤粨銆佹暀瀛︾瓑澶氱璐ｄ换銆傝川閲忔帶鍒跺眰璐熻矗璇佹嵁鏍搁獙銆佹湳璇綊涓€銆佺鍙峰拰鍗曚綅妫€鏌ャ€佸妯″瀷鍙嶉┏瀹＄浠ュ強缃俊搴︽帶鍒躲€傜煡璇嗗眰鍖呮嫭鏈湴鐭ヨ瘑搴撱€佹贩鍚堟绱€佹湳璇〃銆佺鍙疯〃銆佸崟浣嶈〃銆佸伐绋嬭澧冭〃銆佷富棰樺浘璋辩瓑銆傛暟鎹眰鍖呮嫭鍘熷 PDF銆丱CR 鍚?PDF銆佺粨鏋勫寲 JSON/Markdown銆乧hunk 绱㈠紩銆佸悜閲忕储寮曘€佸厓鏁版嵁鏁版嵁搴撳拰鏃ュ織銆?

```text
User
  鈫?
URGENT -> Tutor-Orchestrator
  鈹溾攢 Task Layer
鈹?  鈹溾攢 URGENT -> 鏂囨。鎽勫彇涓庤В鏋?Skill
鈹?  鈹溾攢 URGENT -> 鐭ヨ瘑搴撴绱?Skill
鈹?  鈹溾攢 URGENT -> 姒傚康瑙ｉ噴 / 鎬荤粨闂瓟 Skill
  鈹?  鈹溾攢 宸ョ▼闂鍒嗘瀽 Skill
  鈹?  鈹溾攢 鍏紡涓庢帹瀵?Skill
  鈹?  鈹溾攢 鏂囩尞鐮旂┒妫€绱?Skill
  鈹?  鈹溾攢 妯″瀷閫夋嫨 Skill锛堝寮猴級
  鈹?  鈹斺攢 瀹為獙涓庢祴閲忓缓璁?Skill锛堝寮猴級
  鈹溾攢 Quality Control Layer
  鈹?  鈹溾攢 鏈/绗﹀彿/鍗曚綅瑙勮寖鍖?
  鈹?  鈹溾攢 寮曠敤涓庤瘉鎹牳楠?
  鈹?  鈹溾攢 鍥炵瓟瀹＄
鈹?  鈹斺攢 URGENT -> 杈撳嚭椋庢牸鏁村舰
  鈹溾攢 Knowledge Layer
鈹?  鈹溾攢 URGENT -> 鏈湴鏂囨。搴?
鈹?  鈹溾攢 URGENT -> 娣峰悎妫€绱紙鍙厛浠庣畝鍗曠増鏈捣姝ワ級
  鈹?  鈹溾攢 Glossary / Symbols / Units / Topic Map
  鈹?  鈹斺攢 宸ョ▼璇涓庢渚嬫矇娣€
  鈹斺攢 Data Layer
鈹溾攢 URGENT -> Raw PDFs / OCR PDFs
鈹溾攢 URGENT -> Extracted JSON / Markdown / Images / Tables
      鈹溾攢 PostgreSQL 鍏冩暟鎹?
鈹溾攢 URGENT -> Qdrant 鍚戦噺绱㈠紩
      鈹斺攢 Redis 缂撳瓨 / 浠诲姟鐘舵€?/ 鏃ュ織
```

## 4. 涓轰粈涔堣繖涓郴缁熷繀椤烩€滀笓绮惧寲鈥濊€屼笉鏄€滄硾鍖栬亰澶?+ RAG鈥?

鍒ゆ柇涓€涓郴缁熸槸鍚︿笓绮撅紝涓嶇湅瀹冭兘涓嶈兘鍥炵瓟鎸姩瀛﹂棶棰橈紝鑰岀湅瀹冨湪浠ヤ笅鏂归潰鏄惁鏄庢樉寮轰簬閫氱敤妯″瀷鐩存帴瑙ｆ瀽鏂囨。锛氱涓€锛屾槸鍚︾湡鐨勮兘绋冲畾澶勭悊鏁欐潗銆佹爣鍑嗐€佽鏂囧拰鎵弿浠讹紝鑰屼笉鏄彧鍦ㄥ皯閲忓共鍑€ PDF 涓婂ソ鐢ㄣ€傜浜岋紝鏄惁瀵规尟鍔ㄥ涓殑澶氫箟鏈銆佺鍙峰啿绐併€佸崟浣嶄綋绯诲拰鍏紡閫傜敤鏉′欢鏈夊唴寤烘帶鍒躲€傜涓夛紝鏄惁鑳芥妸宸ョ▼闂涓庡鏈畾涔夊尯鍒嗗紑锛屽苟榛樿浠ュ伐绋嬫剰涔夈€佸墠鎻愭潯浠躲€佸眬闄愭€у拰涓嬩竴姝ュ缓璁潵缁勭粐绛旀銆傜鍥涳紝鏄惁鑳芥妸鐭ヨ瘑娌夋穩涓哄彲澶嶇敤璧勪骇锛屼緥濡傛湳璇簱銆佺鍙疯〃銆佷富棰樺浘鍜屾渚嬫槧灏勶紝鑰屼笉鏄瘡娆￠兘浠庡ご妫€绱€傜浜旓紝鏄惁鑳藉鍥炵瓟杩涜璇佹嵁鏍搁獙锛屽尯鍒嗘枃妗ｆ槑纭啓鍑恒€佹ā鍨嬫帹鏂€佸伐绋嬬粡楠屽拰涓嶇‘瀹氬唴瀹广€?

## 5. 鎶€鏈爤涓庡伐鍏锋爤锛堥閫夋柟妗堬級锛圲RGENT锛?

鍦ㄤ綘鈥滆嚜鐢ㄣ€侀暱鏈熻凯浠ｃ€侀潪涓撲笟宸ョ▼甯堜絾浼氬€熷姪澶氭ā鍨嬪叡鍚屽紑鍙戔€濈殑鍓嶆彁涓嬶紝棣栭€夋妧鏈矾绾垮簲褰撳敖閲忕ǔ銆佸彲璇汇€佽祫鏂欏銆佷究浜庢ā鍨嬪崗鍔╃敓鎴愬拰閲嶆瀯浠ｇ爜銆傛垜鎺ㄨ崘鐨勪富鏍堟槸 Python + FastAPI + PostgreSQL + Qdrant + Redis + PyMuPDF + OCRmyPDF/Tesseract + React/Next.js銆侾ython 鏄閫夛紝鍥犱负鏂囨。瑙ｆ瀽銆丱CR銆佺瀛﹁绠椼€佹绱€丯LP 鍜?agent 缂栨帓鐢熸€侀兘鏈€鎴愮啛锛汧astAPI 閫傚悎鍋氭湰鍦?API 灞傦紱PostgreSQL 璐熻矗鍏冩暟鎹拰缁撴瀯鍖栫储寮曪紱Qdrant 閫傚悎鏈湴閮ㄧ讲 dense/sparse/hybrid 妫€绱紱Redis 鐢ㄤ簬缂撳瓨鍜屼换鍔￠槦鍒楋紱PyMuPDF 閫傚悎鏂囧瓧鐗?PDF 鎻愬彇涓庨〉闈㈢骇鍏冪礌澶勭悊锛汷CRmyPDF + Tesseract 閫傚悎鎶婃壂鎻忕増 PDF 杞垚甯︽枃瀛楀眰鐨勫彲鎼滅储鏂囨。锛涘墠绔彧闇€ React/Next.js 鍗冲彲锛屼笉瑕佹眰涓€寮€濮嬪仛澶嶆潅搴旂敤銆?

## 6. 鏈湴鐭ヨ瘑搴撹璁★細涓嶆槸鈥滃悜閲忓簱鈥濓紝鑰屾槸鈥滆瘉鎹腑鍙扳€濓紙URGENT锛?

鏈湴鐭ヨ瘑搴撲笉鑳借鐞嗚В涓衡€滄妸鏂囨。鍒囩墖鍋?embedding 鐒跺悗鎼溾€濓紝鑰屽簲鐞嗚В涓轰竴涓洿缁曡瘉鎹粍缁囩殑涓彴銆傚畠鑷冲皯瑕佺鐞嗗洓绫昏祫浜э細鍘熷鏂囨。璧勪骇銆佺粨鏋勫寲鏂囨。璧勪骇銆佹绱㈣祫浜у拰璇佹嵁璧勪骇銆傚師濮嬫枃妗ｈ祫浜ф槸 PDF銆佹壂鎻忎欢銆佽涔夈€侀」鐩瑪璁扮瓑锛涚粨鏋勫寲鏂囨。璧勪骇鏄珷鑺傘€佹钀姐€佸叕寮忋€佸浘琛ㄣ€佽〃鏍笺€佸浘棰樸€佹湳璇储寮曘€佺鍙风储寮曪紱妫€绱㈣祫浜ф槸 BM25 绱㈠紩銆佸悜閲忕储寮曘€佹湳璇埆鍚嶈〃銆侀噸鎺掔壒寰侊紱璇佹嵁璧勪骇鏄紩鐢ㄩ敋鐐广€侀〉鐮佹槧灏勩€乧hunk 涓庡洖绛旂殑瀵瑰簲鍏崇郴銆傛病鏈夋渶鍚庤繖涓€灞傦紝绯荤粺灏辨棤娉曞舰鎴愬彲杩芥函浼樺娍銆?

## 7. 鏂囨。鎽勫彇涓庤В鏋愭祦姘寸嚎锛圲RGENT锛?

鏂囨。鍏ュ簱蹇呴』璧扮粺涓€娴佹按绾匡紝涓嶈兘鈥滄湁鏃?OCR锛屾湁鏃剁洿鎺ュ垏鐗囷紝鏈夋椂鍏堥棶绛斺€濄€傛爣鍑嗘祦绋嬪缓璁负锛氭枃妗ｅ垎绫汇€佸幓閲嶅拰鍏冩暟鎹櫥璁般€丱CR 鍒ゆ柇銆佺粨鏋勫寲鎻愬彇銆佽涔夐噸缁勩€乧hunking銆佺储寮曟瀯寤恒€佹湳璇笌绗﹀彿鍥炲～銆佽В鏋愯川閲忔爣璁般€傛壂鎻忕増 PDF 灏嗘槸绯荤粺鏃╂湡鏈€涓昏鐨勭棝鐐广€傜涓€浠ｄ笉搴旇拷姹傗€滃叏鑷姩瀹岀編鎻愬彇鈥濓紝鑰屽簲杩芥眰鈥滃彲鎼滅储銆佸彲寮曠敤銆侀敊璇彲杩借釜銆佸眬閮ㄥ彲浜哄伐淇ˉ鈥濄€?

褰撳墠闃舵鍦ㄧ増闈㈣В鏋愬眰鏆傛椂淇濈暀鈥滃師鐢?PDF 瑙ｆ瀽 + OCR 杈撳嚭缁撴瀯鈥濈殑缁勫悎鏂规锛氭湁楂樿川閲忔枃瀛楀眰鐨?PDF 浼樺厛浣跨敤鍘熺敓瑙ｆ瀽缁撴灉锛屾壂鎻?PDF 鎴栦綆璐ㄩ噺鏂囧瓧灞傞〉闈㈠垯涓昏渚濊禆 OCR 杈撳嚭鐨?block銆乥box銆乸age_no 鍜?confidence 绛夌粨鏋勪俊鎭€傝繖鏍峰仛鐨勭洰鐨勬槸鍏堟妸鐭ヨ瘑搴撳叆鍙ｈ窇閫氥€佷繚璇佸彲鎼滅储涓庡彲寮曠敤锛岃€屼笉鏄湪棣栨湡灏卞紩鍏ユ洿楂橀绮掑害鐨勭嫭绔嬬増闈㈢悊瑙ｅ眰銆?

## 8. 妫€绱㈣璁★細蹇呴』閲囩敤娣峰悎妫€绱紙URGENT锛?

鎸姩瀛﹀満鏅笅锛岀函鍚戦噺妫€绱㈣繙杩滀笉澶燂紝绾叧閿瘝妫€绱篃涓嶅銆傚繀椤婚噰鐢ㄦ贩鍚堟绱細鍏堝仛 query 瑙勮寖鍖栵紝鍐嶈蛋鍏抽敭璇嶅彫鍥炰笌璇箟鍙洖鍙岃矾锛屽啀鍋氳瀺鍚堜笌閲嶆帓搴忋€傚ぇ閲忔煡璇㈠悓鏃跺叿鏈夋湳璇簿纭€у拰璇箟鍙樹綋锛屽洜姝?query 瑙勮寖鍖栥€佹潵婧愪紭鍏堢骇鍜岄噸鎺掗€昏緫閮藉緢鍏抽敭銆傛潵婧愪紭鍏堢骇寤鸿鍥哄畾涓猴細鏍囧噯 > 鏁欐潗 > 缁艰堪 > 鍗曠瘒璁烘枃 > 缃戦〉锛涜嫢闂鏄庣‘瑕佹眰鏈€鏂扮爺绌讹紝鍒欏厑璁歌鏂囧拰缁艰堪浼樺厛銆?

## 9. Taxonomy锛氱湡姝ｄ娇绯荤粺涓撶簿鐨勯暱鏈熻祫浜?

濡傛灉绯荤粺鍙瓨鏂囨湰鍜?embedding锛屽畠鍏呭叾閲忔槸涓€涓細鎼滄枃妗ｇ殑闂瓟鍣ㄣ€傜湡姝ｄ娇瀹冧笓绮剧殑鏄?taxonomy锛屼篃灏辨槸浣犻€愭娌夋穩涓嬫潵鐨勬湳璇€佺鍙枫€佸崟浣嶅拰涓婚鍏崇郴璧勪骇銆傛渶灏戣缁存姢鍥涘琛細glossary銆乻ymbols銆乽nits銆乪ngineering_context / topic_map銆?

## 10. 鏁版嵁搴撴灦鏋勫缓璁紙PostgreSQL 渚э級锛圲RGENT锛?

鏍稿績琛ㄥ缓璁嚦灏戝寘鎷?documents銆乨ocument_sections銆乧hunks銆乫igures_tables銆乼erms銆乻ymbols銆乽nits銆乧itations銆乹a_logs銆傝璁＄洰鏍囦笉鏄竴娆″埌鏋佽嚧锛岃€屾槸鍏堟敮鎸佹枃妗ｅ叆搴撱€佸垎灞傜粨鏋勩€乧hunk 妫€绱€佹湳璇拰绗﹀彿鏄犲皠銆佸洖绛斿紩鐢ㄥ拰閿欒杩借釜銆?

## 11. Skills 鏋舵瀯锛氭帹鑽愭寮忕増鏈紙URGENT锛?

瀵逛綘杩欎釜椤圭洰锛屾渶鍚堢悊鐨勫苟涓嶆槸 skill 瓒婂瓒婂ソ锛岃€屾槸 skill 鐨勮竟鐣岃秺娓呮櫚瓒婂ソ銆傛帹鑽愰噰鐢ㄢ€? 涓牳蹇?skills + 2 涓寮?skills + 4 涓í鍚戞牎楠?鏁村舰 skills鈥濈殑姝ｅ紡鐗堟湰銆?

鑻ヤ互褰撳墠鍒濇湡闇€姹備负鍑嗭紝棣栨壒 URGENT skills 寤鸿鏀剁缉涓?4 涓細S1 鏂囨。鎽勫彇涓庤В鏋愩€丼2 鐭ヨ瘑搴撴绱€丼3 姒傚康瑙ｉ噴 / 鎬荤粨闂瓟銆乂4 杈撳嚭椋庢牸鏁村舰銆傚叾浠?skills 鍙互鍏堜繚鐣欏悕绉颁笌鎺ュ彛锛屼絾涓嶄綔涓洪鏈熶氦浠橀樆濉為」銆?

## 12. 澶氭ā鍨嬪崗浣滆璁?

鍚堢悊鍒嗗伐寰堝叧閿€傛渶浼樺仛娉曚笉鏄鎵€鏈夋ā鍨嬮兘瀵瑰悓涓€闂鍚勭瓟涓€閬嶏紝鑰屾槸鎸夎鑹插垎宸ワ細涓诲洖绛旀ā鍨嬭礋璐ｇ粍缁囨渶缁堢瓟妗堬紝浠ｇ爜瀹炵幇妯″瀷璐熻矗鍐欒В鏋愭祦绋嬨€佹绱笌 API锛屽绋挎ā鍨嬭礋璐ｆ壘鍋锋崲姒傚康涓庡墠鎻愰仐婕忥紝璇佹嵁鏍稿妯″瀷璐熻矗妫€鏌ョ粨璁烘槸鍚︾湡鐨勮鏉ユ簮鏀寔銆傝繍琛岄樁娈靛彧鍦ㄩ珮椋庨櫓鍥炵瓟鏃跺惎鐢ㄥ畬鏁存牎楠岄摼銆?

## 13. 宸ョ▼瀵煎悜杈撳嚭妯℃澘锛圲RGENT锛?

鐢变簬绯荤粺闈㈠悜鐪熷疄椤圭洰锛屾渶缁堝洖绛旀ā鏉垮缓璁浐瀹氫负锛氬厛缁欑粨璁猴紝鍐嶈В閲婂伐绋嬫剰涔夛紝鍐嶅垪閫傜敤鍓嶆彁锛屽啀璇存槑澶辨晥鏉′欢鍜屽父瑙佽鍖猴紝蹇呰鏃剁粰鏈€绠€妯″瀷/鍏紡锛屾渶鍚庣粰涓嬩竴姝ュ缓璁拰璇佹嵁鏍囩銆?

## 14. 寮€鍙戣矾绾夸笌宸ユ湡浼扮畻锛圲RGENT锛?

婕旂ず绾?MVP 鍙互鍦?2鈥? 鍛ㄥ唴瀹屾垚锛屼絾鑻ョ洰鏍囨槸鈥滄槑鏄句笓绮俱€佺ǔ瀹氥€佷紭浜庨€氱敤妯″瀷鐩存帴闂瓟鈥濓紝鏇寸幇瀹炵殑鍖洪棿鏄細涓汉鍙ǔ瀹氫娇鐢ㄧ殑涓€浠ｇ増 6鈥?0 鍛紱杈冨畬鏁翠笓涓氱増 3鈥? 涓湀銆?

濡傛灉瀹屽叏鎸夊綋鍓嶇煭鏈熺洰鏍囨敹缂╄寖鍥达紝鍙柊澧炰竴涓?URGENT 閲岀▼纰戯細鍏堝湪 1-2 鍛ㄥ唴鎵撻€氭枃浠惰鍙栦笌鏂囧瓧鎻愬彇銆佸熀纭€ chunking 涓庣储寮曘€佹憳瑕佷笌闂瓟鎺ュ彛锛屼互鍙婃渶灏忓彲鐢ㄧ殑 CLI 鎴栭〉闈㈠叆鍙ｃ€?

## 15. 椋庨櫓鐐逛笌鐪熷疄闅剧偣

鐪熸闅剧殑鍦版柟涓嶅湪鑱婂ぉ妗嗗拰妯″瀷鎺ョ嚎锛岃€屽湪鏂囨。澶勭悊璐ㄩ噺銆佹绱㈢瓥鐣ャ€佹湳璇拰绗﹀彿缁熶竴銆佽瘉鎹牳楠屻€佸伐绋嬬煡璇嗚〃杈炬柟寮忋€傛渶涓昏椋庨櫓鍖呮嫭锛氭壂鎻?PDF 璐ㄩ噺宸€佸叕寮忓浘琛ㄨВ鏋愪笉绋炽€佷笓涓氭湳璇涔夈€佺鍙峰拰鍗曚綅鍐茬獊銆佺己涔忕幇鍦轰笂涓嬫枃鏃剁粰鍑轰吉纭畾鎬у缓璁紝浠ュ強绯荤粺鍓嶆湡杩囧害璁捐銆?

## 16. 鏈€缁堝畾鍨嬪缓璁紙URGENT锛?

鎺ㄨ崘褰撳墠鐗堟湰鐩存帴閲囩敤锛氫竴涓澶栫粺涓€鐨?Tutor-Orchestrator锛涘簳灞備娇鐢?Python + FastAPI + PostgreSQL + Qdrant + Redis + PyMuPDF + OCRmyPDF/Tesseract + React/Next.js锛涚煡璇嗕晶鏋勫缓鏈湴璇佹嵁涓彴鑰屼笉鏄崟绾悜閲忓簱锛涙绱晶浣跨敤 query 瑙勮寖鍖?+ BM25 + dense retrieval + reranker 鐨勬贩鍚堥摼璺紱鑳藉姏渚ч噰鐢?8 涓牳蹇?skills銆? 涓寮?skills 鍜?4 涓牎楠?鏁村舰 skills锛涢粯璁ゅ洖绛旇寖寮忔槸宸ョ▼妯″紡锛涙墍鏈夊熀浜庢枃妗ｇ殑鍥炵瓟閮藉繀椤诲甫璇佹嵁鏍囩鍜岀疆淇¤竟鐣岋紱鎵€鏈夐暱鏈熶紭鍔块兘閫氳繃 taxonomy銆佹渚嬫矇娣€鍜屽洖褰掓祴璇曠疮绉紝鑰屼笉鏄瘎甯屾湜浜庢ā鍨嬭嚜宸辫秺鏉ヨ秺鎳傛尟鍔ㄥ銆?

鍥犳锛屽綋鍓嶆渶鐜板疄鐨勯鍙戠増鏈簲瀹氫箟涓猴細鍥寸粫鐭ヨ瘑搴撴枃鏈彁鍙栥€佹€荤粨涓庨棶绛旂殑鐭湡鍙敤 Agent锛岃€屼笉鏄竴寮€濮嬪氨浜や粯瀹屾暣涓撲笟鐗堣兘鍔涚煩闃点€?

## 闄勫綍 A锛氱洰褰曠粨鏋勫缓璁?

```text
vibration_agent/
鈹溾攢 apps/
鈹? 鈹溾攢 api/
鈹? 鈹溾攢 worker/
鈹? 鈹斺攢 ui/
鈹溾攢 data/
鈹? 鈹溾攢 raw/
鈹? 鈹溾攢 ocr/
鈹? 鈹溾攢 extracted/
鈹? 鈹溾攢 chunks/
鈹? 鈹溾攢 embeddings/
鈹? 鈹斺攢 exports/
鈹溾攢 db/
鈹? 鈹溾攢 postgres/
鈹? 鈹斺攢 qdrant/
鈹溾攢 configs/
鈹溾攢 taxonomy/
鈹溾攢 prompts/
鈹斺攢 tests/
```

## 闄勫綍 B锛氭暟鎹簱琛ㄥ缓璁紙URGENT锛?

| 琛ㄥ悕 | 浣滅敤 | 鏍稿績瀛楁 |
| --- | --- | --- |
| documents (URGENT) | 鏂囨。涓昏〃 | id, title, type, source, language, year, authors, file_path, ocr_status, parse_status, version, hash |
| document_sections (URGENT) | 绔犺妭灞傜骇 | id, doc_id, parent_id, heading, level, page_start, page_end |
| chunks (URGENT) | 妫€绱㈠熀鏈崟鍏?| id, doc_id, section_id, page_start, page_end, chunk_type, text, normalized_text, token_count, citation_anchor |
| figures_tables | 鍥捐〃涓庡浘棰?| id, doc_id, page_no, kind, caption, image_path, related_chunk_ids |
| terms | 鏈瑙勮寖琛?| id, canonical_term, zh_name, en_name, aliases, notes, topic |
| symbols | 绗﹀彿瑙勮寖琛?| id, canonical_symbol, latex, meaning, unit, notes |
| units | 鍗曚綅瑙勮寖琛?| id, quantity, canonical_units, aliases, warning_notes |
| citations (URGENT) | 鍥炵瓟涓庤瘉鎹槧灏?| answer_id, chunk_id, evidence_type, confidence |
| qa_logs (URGENT) | 闂瓟璁板綍涓庤皟璇?| id, query, intent, chosen_skills, retrieved_chunks, final_verdict |

## 闄勫綍 C锛歋kills 鏋舵瀯鍥撅紙鏂囨湰鐗堬級锛圲RGENT锛?

```text
URGENT -> Tutor-Orchestrator
鈹溾攢 URGENT -> S1 鏂囨。鎽勫彇涓庤В鏋?
鈹溾攢 URGENT -> S2 鐭ヨ瘑搴撴绱?
鈹溾攢 URGENT -> S3 姒傚康瑙ｉ噴 / 鎬荤粨闂瓟
  鈹溾攢 S4 宸ョ▼闂鍒嗘瀽
  鈹溾攢 S5 鍏紡涓庢帹瀵?
  鈹溾攢 S6 鏂囩尞鐮旂┒妫€绱?
  鈹溾攢 S7 妯″瀷閫夋嫨
  鈹溾攢 S8 瀹為獙涓庢祴閲忓缓璁?
  鈹溾攢 V1 鏈/绗﹀彿/鍗曚綅瑙勮寖鍖?
  鈹溾攢 V2 寮曠敤涓庤瘉鎹牳楠?
  鈹溾攢 V3 鍥炵瓟瀹＄
鈹斺攢 URGENT -> V4 杈撳嚭椋庢牸鏁村舰
```

## 闄勫綍 D锛歍axonomy 绀轰緥

glossary_zh_en.yaml

```text
term: transmissibility
zh: 浼犻€掔巼
aliases: [浼犻€掔郴鏁? 鍝嶅簲浼犻€掔巼]
note: 闇€瑕佸尯鍒嗕綅绉讳紶閫掔巼涓庡姏浼犻€掔巼

```

symbols.yaml

```text
symbol: omega_n
latex: \omega_n
meaning: undamped natural angular frequency
unit: rad/s
avoid_confusion_with: [\omega_d, \Omega, f_n]

```

engineering_context.yaml

```text
topic: rotor_unbalance
related_topics: [critical_speed, synchronous_response, balancing]
typical_outputs: [鎸箙, 鐩镐綅, 涓寸晫杞€熷尯闂碷
common_models: [Jeffcott rotor]
```

## 闄勫綍 E锛欽SON I/O 绀轰緥锛圲RGENT锛?

閫氱敤 Skill 杈撳叆

```text
{
  "task_id": "...",
  "user_query": "...",
  "context": {...},
  "retrieval_results": [...],
  "user_mode": "engineering|definition|derivation|research",
  "constraints": {...}
}
```

閫氱敤 Skill 杈撳嚭

```text
{
  "status": "ok|insufficient|fail",
  "summary": "...",
  "structured_result": {...},
  "citations": [...],
  "warnings": [...],
  "handoff_recommendation": "next_skill_name|finalize"
}
```

鐭ヨ瘑搴撴绱?Skill 杈撳嚭

```text
{
  "normalized_query": "half-power bandwidth damping ratio estimation",
  "intent": "definition|comparison|standard_lookup|engineering",
  "hits": [
    {
      "chunk_id": "c_001",
      "doc_id": "book_01",
      "source_type": "book",
      "pages": "134-135",
      "score": 0.92,
      "reason": "contains explicit damping ratio estimation method"
    }
  ]
}
```

宸ョ▼闂鍒嗘瀽 Skill 杈撳嚭

```text
{
  "diagnosis_summary": "...",
  "likely_causes": ["...", "..."],
  "assumptions": ["operating speed near resonance", "sensor mounting is reliable"],
  "recommended_next_checks": ["run-up test", "phase measurement"],
  "modeling_level": "lumped|sdof|mdof|fem|experimental",
  "citations": [...]
}
```

寮曠敤涓庤瘉鎹牳楠?Skill 杈撳嚭

```text
{
  "verdict": "pass|revise|fail",
  "supported_claims": [...],
  "unsupported_claims": [...],
  "citation_map": [...],
  "labels": ["documented", "inferred", "heuristic"]
}

```

## OCR 瀛愮郴缁熻ˉ鍏呰璁★紙鏂板锛夛紙URGENT锛?

鏈妭鐢ㄤ簬姝ｅ紡琛ュ厖 OCR 宸ュ叿閫夊瀷銆佸弻寮曟搸宸ヤ綔娴併€侀樁娈靛疄鏂借寖鍥翠笌鍏ュ簱绛栫暐銆傜粨璁哄厛琛岋細瀵逛簬褰撳墠鎸姩瀛﹀涔犲姪鎵嬮」鐩紝鎺ㄨ崘閲囩敤 鈥淧addleOCR 涓婚摼璺?+ Tesseract 鍏滃簳閾捐矾鈥?鐨勫弻寮曟搸鏂规锛屼絾褰撳墠鍙疄鐜扮涓€闃舵鍜岀浜岄樁娈碉紝涓嶅仛澶ф壒閲忕绾垮悶鍚愪紭鍖栥€傝繖閲岀殑鐩爣涓嶆槸杩芥眰鍗曚竴 OCR 寮曟搸鍦ㄧ悊璁洪€熷害涓婄殑缁濆浼樺娍锛岃€屾槸璁╂壂鎻忕増 PDF銆佺畝浣撲腑鏂囦笌鑻辨枃娣峰悎鏂囨。銆佸鏉傛暀鏉愪笌鏍囧噯椤佃兘澶熺ǔ瀹氳繘鍏ョ煡璇嗗簱锛屽苟涓斿湪鍚庣画妫€绱€佸紩鐢ㄣ€侀棶绛斿拰鐮旂┒杈呭姪涓叿澶囧彲鐢ㄦ€с€?

### 涓€銆佷负浠€涔堝綋鍓嶄笉寤鸿鎶?鈥滄牳蹇冨疄鐜拌瑷€鈥?浣滀负涓诲喅绛栦緷鎹€?

瀵?OCR 瀛愮郴缁熸潵璇达紝绔埌绔€楁椂閫氬父鐢?PDF 娓叉煋銆佸垏椤点€佸浘鍍忛澶勭悊銆佺増闈㈠垎鏋愩€佹枃鏈娴嬨€佹枃鏈瘑鍒€佸悗澶勭悊銆佺粨鏋勯噸寤恒€丣SON/Markdown 杈撳嚭浠ュ強鐭ヨ瘑搴撳啓鍏ュ叡鍚屽喅瀹氾紝鍥犳骞朵笉鑳界畝鍗曞湴鏍规嵁 鈥淭esseract 涓昏浠?C++ 寮€鍙戔€?灏辨帹鏂畠鍦ㄦ暣涓?agent 宸ヤ綔娴侀噷涓€瀹氭洿蹇€備綘鐨勯」鐩綋鍓嶄篃涓嶄互澶ф壒閲忕绾垮鐞嗕负鏍稿績鐩爣锛岃€屾槸浠ヤ腑鑻辨贩鍚堝伐绋嬫枃妗ｇ殑鐭ヨ瘑搴撳彲鐢ㄦ€т负绗竴浼樺厛绾э紝鎵€浠ュ喅瀹氬伐鍏烽€傞厤搴︾殑鍏抽敭鍥犵礌搴斿綋鏄腑鏂囨敮鎸併€佸鏉傜増闈㈠鐞嗚兘鍔涖€佺粨鏋勫寲杈撳嚭鑳藉姏銆佷笌 RAG/Agent 宸ヤ綔娴佺殑鍏煎鎬э紝浠ュ強鍚庣画鏄惁渚夸簬鍋?fallback 涓庝氦鍙夐獙璇併€?

### 浜屻€佷富鏂规涓轰粈涔堟帹鑽?PaddleOCR銆?

缁撳悎浣犲綋鍓嶇殑鏂囨。绫诲瀷鍜岀郴缁熺洰鏍囷紝PaddleOCR 鏇撮€傚悎浣滀负涓?OCR 鏂规銆傜涓€锛屼綘鍚庣画杩涘叆鐭ヨ瘑搴撶殑涓昏鏂囨。涓虹畝浣撲腑鏂囧拰鑻辨枃锛孭addleOCR 鍦ㄤ腑鏂囧満鏅笂澶╃劧鏇磋创杩戜綘鐨勪富闇€姹傦紝鍚屾椂涔熻兘澶熻鐩栬嫳鏂囥€傜浜岋紝浣犱笉鏄湪鍋氬崟寮犲浘鐗?OCR锛岃€屾槸鍦ㄥ仛鏁欐潗銆佹爣鍑嗐€佽鏂囥€佹壂鎻?PDF 鐨勭粨鏋勫寲瑙ｆ瀽锛孭addleOCR 鐨勬暣浣撴柟鍚戞洿鎺ヨ繎鏂囨。鐞嗚В鍏ュ彛锛岃€屼笉浠呬粎鏄紶缁熷瓧绗﹁瘑鍒€傜涓夛紝浣犳暣涓郴缁熺殑鏈€缁堢敤閫旀槸鐭ヨ瘑搴撳叆搴撱€丷AG 妫€绱€佸甫椤电爜寮曠敤闂瓟鍜岀爺绌惰緟鍔╋紝杩欒姹?OCR 缁撴灉灏介噺鍚戠粨鏋勫寲鏂囨。闈犳嫝锛岃€屼笉鏄彧缁欏嚭涓€娈电函鏂囨湰銆傜鍥涳紝PaddleOCR 鏇撮€傚悎琚斁杩?鈥滃厛瑙ｆ瀽銆佸啀缁撴瀯鍖栥€佸啀鍏ュ簱鈥?鐨勪富宸ヤ綔娴佷腑锛屽洜姝ゅ畠鏇寸鍚堜綘褰撳墠 agent 鐨勭郴缁熺洰鏍囥€?

### 涓夈€佷负浠€涔堜笉鎶?Tesseract 浣滀负涓诲紩鎿庯紝浣嗕粛鐒跺缓璁繚鐣欍€?

Tesseract 浠嶇劧鍊煎緱淇濈暀锛屽師鍥犳槸瀹冩垚鐔熴€佺ǔ瀹氥€佽瑷€瑕嗙洊骞裤€佺敓鎬佷赴瀵岋紝涔熼€傚悎浣滀负杞婚噺绾у熀纭€ OCR 鎴栫浜屽紩鎿庤繘琛屼氦鍙夐獙璇併€備絾灏变綘鐨勯」鐩€岃█锛屽畠鏇撮€傚悎鎵紨 fallback 鎴栬ˉ鍏呰鑹诧紝鑰屼笉鏄富閾捐矾瑙掕壊銆傚師鍥犲湪浜庯細绗竴锛屼綘鍚庣画浼氶潰瀵规壂鎻忔暀鏉愩€佽€佹棫 PDF銆佸弻璇枃妗ｃ€佸鏉傜増闈㈤〉锛岃€岃繖浜涢〉闈㈠鏋滃彧渚濊禆浼犵粺 OCR 缁撴灉锛屽線寰€杩橀渶瑕佽嚜宸遍澶栬ˉ寰堝棰勫鐞嗗拰缁撴瀯閲嶅缓宸ヤ綔锛涚浜岋紝浣犵殑鐩爣涓嶆槸鈥滄娊鍒板瓧灏辫鈥濓紝鑰屾槸鈥滄娊鍑虹殑鍐呭瑕佽兘杩涚煡璇嗗簱銆佽兘琚绱€佽兘琚紩鐢ㄢ€濓紱绗笁锛屽綋鍓嶉樁娈典綘鏇撮噸瑙嗙ǔ瀹氬叆搴撲笌涓嬫父鍙敤鎬э紝鑰屼笉鏄璇█鏋侀檺瑕嗙洊鎴栬交閲忛儴缃蹭紭鍏堛€傜患鍚堟潵鐪嬶紝Tesseract 鏇撮€傚悎浣滀负琛ュ厖鍜屼繚闄╋紝鑰屼笉鏄閫変富寮曟搸銆?

### 鍥涖€佹寮忓畾鍨嬬殑 OCR 閫夊瀷缁撹銆傦紙URGENT锛?

褰撳墠椤圭洰鐨?OCR 瀛愮郴缁熷缓璁寮忓畾鍨嬩负锛氫富 OCR 寮曟搸閲囩敤 PaddleOCR锛岃緟鍔?OCR 寮曟搸閲囩敤 Tesseract銆備富閾捐矾浼樺厛澶勭悊鎵€鏈夐渶瑕?OCR 鐨勬枃妗ｉ〉锛岃緟鍔╅摼璺彧鍦ㄦ寚瀹氭潯浠朵笅瑙﹀彂銆傜郴缁熷綋鍓嶄笉杩芥眰澶ц妯℃壒閲忓悶鍚愯兘鍔涳紝涔熶笉浠?鈥滆皝鐞嗚閫熷害鏇村揩鈥?浣滀负閫夊瀷鏍稿績锛岃€屾槸浠?鈥滆皝鏇撮€傚悎涓嫳娣峰悎宸ョ▼鏂囨。瑙ｆ瀽骞舵湇鍔＄煡璇嗗簱鈥?浣滀负涓诲垽鏂爣鍑嗐€?

鍏充簬 Tesseract 鐨勪娇鐢ㄦ柟寮忥紝褰撳墠鐗堟湰鏄庣‘绾﹀畾涓猴細浠呬綔涓?fallback OCR 寮曟搸棰勫鎺ュ叆锛屼笉浣滀负涓婚摼璺紝涓嶈繘琛屼换浣曡嚜涓昏缁冦€傛ā鍨嬩晶浼樺厛棰勫瀹樻柟 tessdata_best 浣滀负 fallback 璇█妯″瀷闆嗗悎锛屽苟缁撳悎 chi_sim銆乪ng銆乷sd 绛夎瑷€鍖呬娇鐢ㄣ€?

### 浜斻€佷袱闃舵瀹炴柦鏂规銆傦紙URGENT锛?

鐜伴樁娈靛彧鍋氫袱姝ャ€傜涓€闃舵鏄?鈥淧addleOCR 涓婚摼璺窇閫氣€濓紝鐩爣鏄鎵弿鐗?PDF 涓庝綆璐ㄩ噺鏂囧瓧灞?PDF 鑳藉缁忚繃 OCR 鍚庤緭鍑轰负鍙户缁粨鏋勫寲澶勭悊鐨勭粨鏋滐紝骞堕『鍒╄繘鍏ョ煡璇嗗簱銆傜浜岄樁娈垫槸鍦ㄤ富閾捐矾绋冲畾鍚庡姞鍏?Tesseract fallback锛屼娇鏌愪簺鍏抽敭椤垫垨鐤戦毦椤靛湪蹇呰鏃跺彲浠ヨ繘琛屼簩娆¤瘑鍒垨浜ゅ弶楠岃瘉銆傝繖閲岀殑閲嶇偣涓嶆槸绔嬪埢鍋氬鏉傜殑澶氬紩鎿庤皟搴︾郴缁燂紝鑰屾槸鍏堜繚璇佷富閾捐矾鍙敤锛屽啀閫愭鎻愬崌椴佹鎬с€?

- URGENT锛氱涓€闃舵鐩爣锛氫娇鐢?PaddleOCR 浣滀负榛樿 OCR 鍏ュ彛锛屼紭鍏堣В鍐崇畝浣撲腑鏂囦笌鑻辨枃娣峰悎鏂囨。銆佹壂鎻忕増鏁欐潗銆佹爣鍑?PDF 绛夎祫鏂欑殑鍙悳绱㈠寲鍜屽彲缁撴瀯鍖栭棶棰樸€傝闃舵瑕佹眰鑷冲皯杈炬垚浠ヤ笅缁撴灉锛氭枃妗ｈ兘澶熸垚鍔熷垏椤靛苟閫佸叆 OCR锛汷CR 杈撳嚭鑳藉鍜岄〉鐮佷俊鎭粦瀹氾紱璇嗗埆缁撴灉鑳藉杩涘叆鍚庣画 chunking 涓庣煡璇嗗簱鍏ュ簱娴佺▼锛涢棶绛旂郴缁熷湪寮曠敤鏃惰兘澶熷洖閾惧埌鍘熷椤点€?
- 绗簩闃舵鐩爣锛氬湪涓婚摼璺窇閫氬悗锛屼负鍏抽敭椤靛拰鐤戦毦椤靛鍔?Tesseract 鍏滃簳鍒嗘敮銆傝鍒嗘敮涓嶉粯璁ゅ叏閲忚繍琛岋紝鍙湪婊¤冻瑙﹀彂鏉′欢鏃跺惎鐢紝渚嬪 PaddleOCR 椤甸潰缃俊搴︽槑鏄惧亸浣庛€佺増闈㈢粨鏋勬娊鍙栧け璐ャ€佽€佹棫鎵弿椤垫晥鏋滃樊銆佹垨浣犲笇鏈涘鏌愪簺鍏抽敭椤甸潰杩涜鍙屽紩鎿庝氦鍙夐獙璇併€傜浜岄樁娈电殑鐩爣鏄彁楂樼ǔ鍋ユ€э紝鑰屼笉鏄浛鎹富閾捐矾銆?
### 鍏€佸缓璁殑 OCR 宸ヤ綔娴併€傦紙URGENT锛?

鎺ㄨ崘鎶?OCR 瀛愮郴缁熸帴鍏ョ幇鏈夋枃妗ｆ憚鍙栫绾匡紝褰㈡垚涓€鏉℃竻鏅扮殑鎵ц閾撅細涓婁紶鍘熷鏂囨。鍚庯紝绯荤粺鍏堝垽鏂 PDF 鏄惁宸插叿澶囬珮璐ㄩ噺鏂囧瓧灞傦紱濡傛灉鏂囧瓧灞傚厖鍒嗕笖鎶藉彇璐ㄩ噺鍙帴鍙楋紝鍒欑洿鎺ヨ繘鍏ョ粨鏋勫寲瑙ｆ瀽锛涘鏋滄枃瀛楀眰涓虹┖銆佺己澶变弗閲嶆垨鎶藉彇璐ㄩ噺涓嶇ǔ瀹氾紝鍒欒繘鍏?OCR 鍒嗘敮銆傝繘鍏?OCR 鍒嗘敮鍚庯紝榛樿鍏堣皟鐢?PaddleOCR 瀹屾垚椤甸潰璇嗗埆涓庡熀纭€缁撴瀯鍖栫粨鏋滅敓鎴愶紝鍐嶅皢缁撴灉閫佸叆鍚庣画鐨勬枃妗ｅ垎鍧椼€佹湳璇綊涓€銆佸悜閲忓寲涓庣煡璇嗗簱鍐欏叆娴佺▼銆傚彧鏈夊綋椤甸潰鍦ㄨ瘑鍒川閲忎笂瑙﹀彂棰勮寮傚父鏉′欢鏃讹紝鎵嶄細棰濆璋冪敤 Tesseract 浣滀负鍏滃簳鍒嗘敮銆?

鍦ㄨ繖涓€闃舵锛孫CR 缁撴灉杩涘叆鐭ヨ瘑搴撳墠鐨勭増闈㈢粨鏋勬暣鐞嗕粛浠ュ師鐢熻В鏋愮粨鏋滃拰 OCR 杈撳嚭涓轰富锛屼笉棰濆寮曞叆楂樺鏉傚害鐨?VLM 鐗堥潰鐞嗚В灞傛潵鍖呮徑 layout analysis銆傚悗缁嫢鏃堕棿鍜岃瘎娴嬭祫婧愬厑璁革紝鍐嶆妸鏍囬灞傜骇銆佸鏍忛槄璇婚『搴忋€佸鏉傝〃鏍煎拰寮傚父椤甸潰鐨勯珮棰楃矑搴︿紭鍖栨媶鎴愮嫭绔嬪崌绾ч」銆?

### 涓冦€佸缓璁殑 fallback 瑙﹀彂鏉′欢銆?

涓轰簡閬垮厤绗簩闃舵鎶婄郴缁熷仛寰楄繃閲嶏紝寤鸿鍙湪鏈夐檺涓旀槑纭殑鍦烘櫙涓嬭Е鍙?Tesseract銆傚彲閲囩敤鐨勮Е鍙戞潯浠跺寘鎷細椤甸潰 OCR 缃俊搴︿綆浜庨槇鍊硷紱椤甸潰瀛樺湪澶ч噺鐤戜技涔辩爜銆佺己瀛椼€侀敊琛屾垨鏂垪锛涢〉闈㈣鍒ゅ畾涓鸿€佹棫鎵弿浠朵笖 PaddleOCR 杈撳嚭鏂囨湰绋€鐤忥紱椤甸潰灞炰簬鍏抽敭璇佹嵁椤碉紝渚嬪浣犲悗缁渶瑕侀珮绮惧害寮曠敤鐨勬爣鍑嗗畾涔夐〉銆佸叕寮忛〉鎴栫粨璁洪〉锛涙垨鑰呬綘甯屾湜瀵规煇浜涢珮浠峰€奸〉闈㈠仛鍙屽紩鎿庝氦鍙夐獙璇併€傝Е鍙戝悗锛岀郴缁熷彲灏?Tesseract 缁撴灉涓?PaddleOCR 缁撴灉杩涜绠€鍗曟瘮瀵癸紝鎷╀紭淇濈暀锛屾垨淇濈暀鍙岀増鏈緵鍚庣画浜哄伐澶嶆牳銆?

### 鍏€丱CR 缁撴灉濡備綍杩涘叆鐭ヨ瘑搴撱€傦紙URGENT锛?

杩欎竴閮ㄥ垎瑕佷笌鍓嶉潰宸茬粡璁捐濂界殑鏈湴鐭ヨ瘑搴撴灦鏋勪繚鎸佷竴鑷淬€侽CR 杈撳嚭涓嶅簲鍙槸绾枃鏈枃浠讹紝鑰屽簲灏介噺杞寲涓哄甫椤电爜銆佸甫鍧楃骇缁撴瀯銆佸彲鍥為摼鐨勪腑闂寸粨鏋溿€傛渶灏忓叆搴撳崟鍏冭嚦灏戝簲鍖呭惈锛歞oc_id銆乸age_no銆乥lock_id銆乺aw_text銆乶ormalized_text銆乥box 鎴栧潡浣嶇疆淇℃伅銆乷cr_engine銆乧onfidence銆乴anguage_guess銆乸arse_status銆傞殢鍚庡啀杩涘叆 section 閲嶇粍銆乧hunking銆佹湳璇槧灏勫拰 embedding銆傝繖鏍峰仛鐨勬剰涔夊湪浜庯紝鍚庣画闂瓟濡傛灉瑕佸紩鐢ㄦ煇涓畾涔夋垨鍏紡锛屼笉鍙槸鑳借鈥滃湪杩欐湰涔﹂噷鍑虹幇杩団€濓紝鑰屾槸鑳藉敖閲忓畾浣嶅埌鍏蜂綋椤靛拰鍏蜂綋娈佃惤銆?

### 涔濄€丱CR 瀛愮郴缁熶笌鐜版湁鏁版嵁搴撴灦鏋勭殑琛旀帴寤鸿銆傦紙URGENT锛?

濡傛灉浣犲悗缁户缁部鐢ㄦ鍓嶅缓璁殑 documents銆乨ocument_sections銆乧hunks銆乫igures_tables銆乼erms銆乻ymbols 绛夎〃锛岄偅涔?OCR 琛ュ厖瀛楁寤鸿鑷冲皯澧炲姞鍦ㄦ枃妗ｉ〉绾ф垨鍧楃骇缁撴灉琛ㄤ腑锛屽寘鎷細ocr_engine銆乷cr_confidence銆乷cr_version銆乷cr_run_time銆乶eeds_review銆乫allback_used銆乫allback_engine銆乼ext_density銆乴ayout_quality銆傝繖鏍蜂綘鍚庢湡灏辫兘鍩轰簬杩欎簺瀛楁鍋氶〉闈㈣川閲忚拷韪€侀棶棰橀〉鍥炴崬鍜屼汉宸ュ鏍革紝鑰屼笉闇€瑕佹瘡娆￠兘閲嶆柊璺戝畬鏁存枃妗ｃ€?

### 鍗併€佸缓璁繚鐣欑殑 OCR 鍏冩暟鎹?JSON 绀轰緥銆傦紙URGENT锛?

```text
{
  "doc_id": "book_001",
  "page_no": 87,
  "ocr_required": true,
  "primary_engine": "paddleocr",
  "fallback_used": false,
  "ocr_confidence": 0.93,
  "layout_quality": "medium",
  "raw_text": "...",
  "normalized_text": "...",
  "blocks": [
    {"block_id": "p87_b1", "text": "...", "bbox": [x1, y1, x2, y2]},
    {"block_id": "p87_b2", "text": "...", "bbox": [x1, y1, x2, y2]}
  ],
  "needs_review": false
}
```

### 鍗佷竴銆佸綋鍓嶉樁娈典笉寤鸿鍋氱殑浜嬫儏銆?

涓轰簡鎺у埗澶嶆潅搴︼紝褰撳墠涓嶅缓璁竴寮€濮嬪氨鍋氫笁浠朵簨銆傜涓€锛屼笉瑕佷竴涓婃潵灏辫拷姹傚寮曟搸骞跺彂銆佹壒閲忚皟搴﹀拰鍚炲悙浼樺寲锛屽洜涓轰綘鐜板湪骞舵病鏈夋槑鏄剧殑澶ц妯＄绾块渶姹傘€傜浜岋紝涓嶈绔嬪埢杩芥眰澶嶆潅鍏紡 OCR銆佸浘琛ㄨ涔夌悊瑙ｅ拰鍏ㄨ嚜鍔ㄥ畬缇庣粨鏋勬仮澶嶏紝鍥犱负杩欎細杩呴€熸妸绯荤粺澶嶆潅搴︽姮楂樸€傜涓夛紝涓嶈鎶?Tesseract 鍜?PaddleOCR 涓€寮€濮嬮兘鍋氭垚瀵圭瓑涓婚摼璺紝鍥犱负杩欎細澧炲姞璋冭瘯涓庣淮鎶ゆ垚鏈€傚綋鍓嶆渶鍚堢悊鐨勮矾绾夸粛鐒舵槸锛氬厛璁?PaddleOCR 鎶婄煡璇嗗簱鍏ュ彛鎵撻€氾紝鍐嶆妸 Tesseract 鎺ユ垚鏈夎竟鐣岀殑鍏滃簳妯″潡銆?

鍚屾椂锛屽綋鍓嶄笉寤鸿鍥犱负杩芥眰鏇寸粏鐨?layout 鑳藉姏鑰屾彁鍓嶉噸鏋勬暣鏉＄増闈㈣В鏋愰摼銆傞鏈熷簲浼樺厛淇濊瘉鍘熺敓瑙ｆ瀽涓?OCR 杈撳嚭鐨勪腑闂寸粨鏋勭ǔ瀹氬彲钀藉簱锛岀瓑鐪熷疄鏂囨。璇勬祴绉疮鍒颁竴瀹氳妯″悗锛屽啀鍐冲畾鏄惁鎶婇珮棰楃矑搴︾増闈㈠垎鏋愭媶鎴愮嫭绔嬪眰銆?

### 鍗佷簩銆佽繖涓€琛ュ厖瀵规€绘垚璁捐鐨勫奖鍝嶃€?

鍔犲叆杩欎竴 OCR 瀛愮郴缁熻ˉ鍏呭悗锛屼綘鍘熸湁鐨勪笁姝ヨ蛋璁捐涓嶉渶瑕佹帹缈伙紝鍙渶瑕佸湪鏂囨。鎽勫彇涓庤В鏋愬瓙绯荤粺涓寮忓姞鍏?鈥淥CR 鍙屽紩鎿庝富鍓柟妗堚€濄€傝繖浼氳浣犵殑绯荤粺鍦ㄦ壂鎻?PDF銆佺畝涓?鑻辨枃璧勬枡鍜屽鏉傚伐绋嬫枃妗ｅ満鏅笅鏇寸ǔ锛屽悓鏃朵篃涓嶄細杩囨棭鎶婄郴缁熷甫鍏ラ珮澶嶆潅搴︺€佸寮曟搸楂樺悶鍚愪紭鍖栭樁娈点€傛崲鍙ヨ瘽璇达紝杩欎竴琛ュ厖涓嶆槸鏀瑰彉鎬讳綋鏋舵瀯锛岃€屾槸鎶婃€讳綋鏋舵瀯閲屾渶瀹规槗鎴愪负鐥涚偣鐨勫叆鍙ｇ幆鑺傚叿浣撳寲銆佸伐绋嬪寲銆?---

# Design Addendum: Agent-Owned Skills And Dual-API Routing

This addendum updates the earlier single-model assumption. The project should not
bind its skill system to either Anthropic-native Skills or OpenAI-native tool
calling. Skills are project-owned assets. Model providers are interchangeable
reasoning and execution backends.

## Skill Ownership

The project should maintain a vendor-neutral agent skill layer:

```text
agent_skills/
  s1_ingestion/
    SKILL.md
    references/
    scripts/
```

This layer defines the agent-facing behavior: when to use the skill, what inputs
are required, what outputs are valid, what not to do, and how to recover from
failure. The deterministic implementation remains in `src/vibration_agent/skills/`
and must continue to use `SkillInput` / `SkillOutput` contracts.

This design allows GPT and Claude to consume the same skill descriptions while
using the same Python runtime implementation underneath.

## Routing Policy

The default operating mode is GPT-first:

- low difficulty: GPT handles end-to-end
- medium difficulty: GPT handles end-to-end
- high difficulty: GPT handles end-to-end unless stakeholder policy overrides
- extreme difficulty: activate the Opus-supervised loop

The routing standard must be stakeholder-defined and configurable. The model may
recommend a difficulty level, but it should not have unrestricted authority to
promote ordinary tasks into the expensive Opus path.

## Extreme Supervisor Loop

Extreme tasks use the following chain:

```text
Opus framework design / decomposition / risk definition
  -> GPT execution / implementation / tests / candidate answer
  -> Opus senior supervisor review
  -> if issues found and loop_count < 2: GPT correction, then Opus review
  -> if issues remain after two loops: Opus takes ownership
  -> final output
```

Opus is therefore reserved for the cases where its stronger framework reasoning
and review quality justify latency and token cost. High difficulty alone is not
sufficient to trigger Opus.

## Scope Constraint

This control-plane upgrade does not change Phase-0 domain scope. S1, S2, S3, and
V4 remain the only active Phase-0 domain chain. Deferred skills stay deferred.
## Obj11.5 - Agent-owned skill registry and model routing design

Objective 11.5 is a control-plane objective inserted between S1 ingestion and S2
retrieval. It does not add new domain capability and does not activate deferred
skills. Its purpose is to make the skill layer vendor-neutral and prepare the
future dual-API routing structure.

In scope:

- create a project-owned `agent_skills/<skill_id>/SKILL.md` package layout
- keep runtime implementations in `src/vibration_agent/skills/*.py`
- define a difficulty routing policy where low, medium, and high default to GPT
- reserve Opus-supervised execution for extreme tasks only
- define model role registry abstractions for GPT and Opus backends
- define supervisor-loop schemas for extreme task plan, execution, review, and revision
- prove through tests that low, medium, and high do not call or require Opus by default

Out of scope:

- real OpenAI or Anthropic API calls
- automatic implementation of S4-S8 or V1-V3
- replacing deterministic Python skills with model-native skill mechanisms

Acceptance:

- `agent_skills/s1_ingestion/SKILL.md` exists and describes S1 from the agent-facing perspective
- `src/vibration_agent/agent/` contains routing, model registry, skill registry, and supervisor schemas
- `configs/app.yaml` records GPT-first routing policy and Opus-only extreme routing
- tests cover routing defaults, explicit extreme escalation, repeated-failure escalation, skill package loading, and supervisor-loop transition rules
