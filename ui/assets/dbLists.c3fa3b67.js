var t=Object.defineProperty,e=Object.getOwnPropertySymbols,a=Object.prototype.hasOwnProperty,s=Object.prototype.propertyIsEnumerable,i=(e,a,s)=>a in e?t(e,a,{enumerable:!0,configurable:!0,writable:!0,value:s}):e[a]=s,o=(t,o)=>{for(var n in o||(o={}))a.call(o,n)&&i(t,n,o[n]);if(e)for(var n of e(o))s.call(o,n)&&i(t,n,o[n]);return t};"undefined"!=typeof require&&require;import{n,_ as l}from"./index.b4e70f3f.js";import{A as r}from"./api_dbManage.c76fae4d.js";import d from"./taskLog.95f9a65c.js";import"./vendor.194c4086.js";import"./index.dfdb83b1.js";import"./bus.d56574c1.js";const c={};var p=n({name:"dbLists",data:()=>({filters:{name:""},upperLevelDb:0,total:0,page:1,size:20,loading:!1,pageLoading:!1,dbShowList:[{label2:"创建PolarDB实例",type:1,isShow:!0,dbType:11},{label2:"创建PostgreSQL实例",type:2,isShow:!0,dbType:1}],rows:[],addType:1,createType:1,databaseInfo:{},switchDataBaseShow:!1,dataBaseShow:!1,createPostgresDatabaseShow:!1,createPolarDBDatabaseShow:!1,pfsDilatationShow:!1,databaseId:"",databaseData:"",colData:[{title:"数据库",istrue:!0},{title:"上级库",istrue:!0},{title:"集群ID",istrue:!0},{title:"状态",istrue:!0},{title:"数据库名称",istrue:!0},{title:"版本",istrue:!0},{title:"数据库类型",istrue:!0},{title:"所在主机",istrue:!0},{title:"机房名称",istrue:!0},{title:"端口",istrue:!0},{title:"数据库目录",istrue:!0},{title:"主备库",istrue:!0}],needToFirstPage:!1,checkBoxGroup:[],checkedColumns:[],pgTypeText:"",isLoginShow:!0,language:""}),components:{editmsgTab:()=>l((()=>import("./editMsgTab.cf3bb43f.js")),["assets/editMsgTab.cf3bb43f.js","assets/editMsgTab.22deea2b.css","assets/index.b4e70f3f.js","assets/index.738ab243.css","assets/vendor.194c4086.js","assets/api_dbManage.c76fae4d.js","assets/index.dfdb83b1.js","assets/bus.d56574c1.js"]),standbyPage:()=>l((()=>import("./createStandbyPage.e77e0f31.js")),["assets/createStandbyPage.e77e0f31.js","assets/createStandbyPage.744ee38d.css","assets/api_dbManage.c76fae4d.js","assets/index.dfdb83b1.js","assets/vendor.194c4086.js","assets/bus.d56574c1.js","assets/index.b4e70f3f.js","assets/index.738ab243.css","assets/verificationRules.bef90446.js"]),switchPage:()=>l((()=>import("./switchDatabasePage.4e8e21fc.js")),["assets/switchDatabasePage.4e8e21fc.js","assets/baseInfo.139b0e47.css","assets/api_dbManage.c76fae4d.js","assets/index.dfdb83b1.js","assets/vendor.194c4086.js","assets/bus.d56574c1.js","assets/index.b4e70f3f.js","assets/index.738ab243.css"]),taskLog:d,editconfigTab:()=>l((()=>import("./editConfigTab.55bfd7cf.js")),["assets/editConfigTab.55bfd7cf.js","assets/editConfigTab.50e8ddce.css","assets/index.b4e70f3f.js","assets/index.738ab243.css","assets/vendor.194c4086.js"]),OperCluster:()=>l((()=>import("./OperCluster.72755b99.js")),["assets/OperCluster.72755b99.js","assets/OperCluster.3234b22b.css","assets/polarDbComputerRoomConfig.955a47ab.js","assets/polarDbComputerRoomConfig.c4d81c89.css","assets/api_clusterManage.788b7961.js","assets/index.dfdb83b1.js","assets/vendor.194c4086.js","assets/bus.d56574c1.js","assets/verificationRules.bef90446.js","assets/staticTools.84335405.js","assets/index.b4e70f3f.js","assets/index.738ab243.css","assets/clusterInfo.098607a8.js","assets/clusterInfo.7c62c11d.css","assets/taskLog.95f9a65c.js","assets/baseInfo.139b0e47.css"]),createPostgresDatabase:()=>l((()=>import("./createPostgresDatabase.cf4919b7.js")),["assets/createPostgresDatabase.cf4919b7.js","assets/createPostgresDatabase.a0a2e5be.css","assets/api_dbManage.c76fae4d.js","assets/index.dfdb83b1.js","assets/vendor.194c4086.js","assets/bus.d56574c1.js","assets/index.b4e70f3f.js","assets/index.738ab243.css","assets/verificationRules.bef90446.js","assets/staticTools.84335405.js"]),createPolarDBDatabase:()=>l((()=>import("./createPolarDBDatabase.6bf542d7.js")),["assets/createPolarDBDatabase.6bf542d7.js","assets/createPolarDBDatabase.46d12874.css","assets/index.b4e70f3f.js","assets/index.738ab243.css","assets/vendor.194c4086.js","assets/api_dbManage.c76fae4d.js","assets/index.dfdb83b1.js","assets/bus.d56574c1.js","assets/verificationRules.bef90446.js","assets/staticTools.84335405.js"]),pfsDilatation:()=>l((()=>import("./pfsDilatation.6cb818c9.js")),["assets/pfsDilatation.6cb818c9.js","assets/pfsDilatation.1f4dcd57.css","assets/api_dbManage.c76fae4d.js","assets/index.dfdb83b1.js","assets/vendor.194c4086.js","assets/bus.d56574c1.js","assets/staticTools.84335405.js","assets/index.b4e70f3f.js","assets/index.738ab243.css"]),viewDatabaseLogs:()=>l((()=>import("./viewDatabaseLogs.74d63082.js")),["assets/viewDatabaseLogs.74d63082.js","assets/viewDatabaseLogs.52746f97.css","assets/api_dbManage.c76fae4d.js","assets/index.dfdb83b1.js","assets/vendor.194c4086.js","assets/bus.d56574c1.js","assets/staticTools.84335405.js","assets/index.b4e70f3f.js","assets/index.738ab243.css"])},mounted(){const t=this;t.language=localStorage.getItem("language_clup");let e=window.location.href.split("?")[1];new URLSearchParams(e).has("token")&&(t.isLoginShow=!1),this.colData.forEach(((t,e)=>{this.checkBoxGroup.push(t.title),this.checkedColumns.push(t.title)})),this.checkedColumns=this.checkedColumns;let a=this.rows;null!=a&&(this.checkedColumns=this.checkedColumns.filter((t=>!a.includes(t)))),r.getPgFamilyInfo().then((function(e){t.pgTypeText=e.pg_family_name,t.dbShowList[1].label2="创建"+e.pg_family_name+"实例",t.getDBList()}))},watch:{checkedColumns(t,e){let a=this.checkBoxGroup.filter((e=>!t.includes(e)));localStorage.setItem(this.rows,JSON.stringify(a)),this.colData.filter((t=>{-1!=a.indexOf(t.title)?t.istrue=!1:t.istrue=!0}))},"filters.name"(t,e){t!=e&&""!=t&&(this.needToFirstPage=!0)}},methods:{openClusterDialog:function(t){let e={page_size:this.size,page_num:this.page,cluster_id:t.cluster_id,cluster_name:t.cluster_name,cluster_type:t.cluster_type};this.$refs.OperCluster.openDialog(e)},funChandleClick:function(t){const e=this;let a="",s=window.location.href.split("?")[1],i=new URLSearchParams(s);i.has("hidmenu")&&(a=i.get("hidmenu")),"conversation"==t.type?e.wantConversationBtn(t.row,a):"lock"==t.type&&e.wantLockBtn(t.row,a)},wantConversationBtn:function(t,e){this.$router.push({path:"/SessionManage",query:o({data:t},""!=e&&{hidmenu:e})})},wantLockBtn:function(t,e){this.$router.push({path:"/lockManage",query:o({data:t},""!=e&&{hidmenu:e})})},composeValue:(t,e,a)=>({type:t,index:e,row:a}),closeDialog(){console.log("执行了"),this.getDBList()},openTaskDialog(t){const e=this;e.$nextTick((function(){e.$refs.tasklog.openDialog(t,"",3)}))},filterFunHandle(t){const e=this;"allchecked"===t?e.colData.forEach(((t,a)=>{e.checkedColumns.push(t.title)})):"cancel"===t&&(this.checkedColumns=[])},tableRowClassName:({row:t,rowIndex:e})=>t.showcolor?"warning-row":"success-row",handleSizeChange(t){this.size=t,this.needToFirstPage=!0,this.getDBList()},formloding(){this.pageLoading=!0},formlodingDown(){this.pageLoading=!1},closePopup(){this.dataBaseShow=!1,this.switchDataBaseShow=!1,this.createPostgresDatabaseShow=!1,this.createPolarDBDatabaseShow=!1,this.pageLoading=!1,this.pfsDilatationShow=!1,this.getDBList()},handleCurrentChange(t){this.page=t,this.getDBList()},handleClick(t){const e=this;switch(t.type){case"1":e.editDBFn(t.index,t.row);break;case"2":e.delDatabase(t.index,t.row);break;case"3":e.addAlarmDefinition(t.index,t.row);break;case"4":e.restartSubmit(t.index,t.row);break;case"7":e.databaseId=t.row.db_id;let a={db_id:t.row.db_id};r.getMasterInfo(a).then((function(t){e.databaseInfo=t,e.dataBaseShow=!0}));break;case"8":e.switchDataBaseShow=!0,e.databaseData=t.row;break;case"9":e.pgPromote(t.row);break;case"11":e.editDBQueryConf(t.row);break;case"12":e.pfsDilatationShow=!0,e.databaseData=t.row;break;case"13":e.$refs.viewDatabaseLogs.openDialog(t.row)}},editDBQueryConf(t){this.$refs.editconfigTab.openDialog(t)},handleSearch(){this.getDBList()},handleSearchByUpper(t){this.upperLevelDb=t,this.needToFirstPage=!0,this.getDBList()},pgPromote:function(t){const e=this;let a="";a=t.cluster_id?this.$t("dbList.activation-message-one")+t.db_id+this.$t("dbList.activation-message-two")+t.cluster_id+this.$t("dbList.activation-message-three"):this.$t("dbList.activation-message-four")+t.db_id+this.$t("dbList.activation-message-five"),this.$confirm(a,this.$t("index.ti-shi"),{type:"warning",closeOnClickModal:!1}).then((()=>{e.loading=!0;let a={db_id:t.db_id};r.pgPromote(a).then((function(){e.loading=!1,e.getDBList()}),(function(t){e.loading=!1}))})).catch((()=>{}))},getDBList:function(){let t=this;t.needToFirstPage&&(t.page=1),1==t.page&&(t.total=0);let e={page_size:t.size,page_num:t.page};0!==t.upperLevelDb&&(t.filters.name="",e.upper_level_db=t.upperLevelDb),""!==t.filters.name&&(e.filter=t.filters.name),t.loading=!0,r.getAllDbList(e).then((function(e){if(t.loading=!1,t.needToFirstPage=!1,t.upperLevelDb=0,e&&e.rows){t.total=e.total;let a=e.rows,s=!1;for(let t=0;t<a.length;t++)a[t].major_version=Number(a[t].version.split(".")[0]),0==t||a[t].cluster_id==a[t-1].cluster_id||(s=!s),a[t].showcolor=s;t.rows=a,t.$nextTick((()=>{t.$emit("btnHidden")}))}}),(function(e){t.loading=!1}))},createDbDialog:function(t){const e=this;1===t?(e.createPolarDBDatabaseShow=!0,e.createType=t):(e.createPostgresDatabaseShow=!0,e.createType=t)},addAlarmDefinition:function(t,e){let a=this;this.$confirm(this.$t("dbList.gaishujuku-message")+e.db_id+this.$t("dbList.haimeiyou-tianjia-message"),this.$t("index.ti-shi"),{type:"warning",closeOnClickModal:!1}).then((()=>{a.loading=!0;let t={object_id:e.db_id,obj_type:"db"};r.addAlarmAPI(t).then((function(){a.loading=!1,a.getDBList()}),(function(t){a.loading=!1}))})).catch((()=>{}))},delDatabase:function(t,e){let a=this;this.$createElement,this.$prompt(`<p>${a.$t("dbList.queren-jiang-message")}(id = ${e.db_id},ip = ${e.host} )\n\t\t\t${a.$t("dbList.shanchu-ma")}(${a.$t("dbList.cicaozuo-hui-message")})\n\t\t\t<p><p>${a.$t("dbList.shifou-shanchu-message")}</p>\n\t\t\t<p id="p" style="display:inline-block"><input class="ischeckInput" name="ischeckInput" type="radio" id="dbdefined_radio_rm_pgdata_yes" value=true> <label for="r">${a.$t("dbList.shi")}</label></p>   <p id="p" style="display:inline-block"><input type="radio" checked  name="ischeckInput"  class="ischeckInput" id="a" value=false> <label for="a">${a.$t("dbList.fou")}</label></p>`,a.$t("index.ti-shi"),{confirmButtonText:this.$t("index.que-ding"),cancelButtonText:this.$t("index.qu-xiao"),customClass:"inputbox",dangerouslyUseHTMLString:!0,closeOnClickModal:!1,inputValidator:t=>t===this.$t("dbList.queren-shanchu"),inputErrorMessage:this.$t("dbList.qingshuru-queren-shanchu"),inputPlaceholder:this.$t("dbList.qingshuru-queren-sahnchu-message")}).then((({value:t})=>{a.loading=!0;let s={db_id:e.db_id,rm_pgdata:!1};document.getElementById("dbdefined_radio_rm_pgdata_yes").checked&&(s.rm_pgdata=!0,console.log("rm_pgdata is true .")),r.deleteInstance(s).then((function(){a.loading=!1;let t=Math.ceil((a.total-1)/a.size),e=a.page>t?t:a.page;a.page=e<1?1:e,a.getDBList()}),(function(t){a.loading=!1,a.getDBList()}))})).catch((t=>{console.log("删除数据库时前端发生错误：",t)}))},editDBFn(t,e){this.$refs.editmsgTab.openDialog(e)},startSubmit:function(t,e){let a=this;this.$confirm(this.$t("dbList.quren-qidong-message")+e.db_id+this.$t("dbList.ma"),this.$t("index.ti-shi"),{type:"warning",closeOnClickModal:!1}).then((()=>{a.loading=!0;let t={db_id:e.db_id};r.startInstance(t).then((function(){a.loading=!1,a.getDBList()}),(function(t){a.loading=!1}))})).catch((()=>{}))},restartSubmit:function(t,e){let a=this;this.$confirm(this.$t("dbList.queren-chongqi-message")+e.db_id+this.$t("dbList.ma"),this.$t("index.ti-shi"),{type:"warning",closeOnClickModal:!1}).then((()=>{a.loading=!0;let t={db_id:e.db_id};r.restartInstance(t).then((function(){a.loading=!1,a.getDBList()}),(function(t){a.loading=!1}))})).catch((()=>{}))},stopSubmit:function(t,e){let a=this;this.$confirm(this.$t("dbList.queren-tingzhi-message")+e.db_id+this.$t("dbList.ma"),this.$t("index.ti-shi"),{type:"warning",closeOnClickModal:!1}).then((()=>{a.loading=!0;let t={db_id:e.db_id};r.stopInstance(t).then((function(){a.loading=!1,a.getDBList()}),(function(t){a.loading=!1}))})).catch((()=>{}))},recleI18nFunc(t){return this.$t("dbList."+t)?this.$t("dbList."+t):t}}},(function(){var t=this,e=t.$createElement,a=t._self._c||e;return a("el-row",{directives:[{name:"loading",rawName:"v-loading",value:t.pageLoading,expression:"pageLoading"}],staticClass:"warp",attrs:{"element-loading-text":t.$t("Public.ping-ming-jia-zai-zhong")}},[a("el-col",{staticClass:"warp-breadcrum",attrs:{span:24}},[a("el-breadcrumb",{attrs:{separator:"/"}},[a("el-breadcrumb-item",[a("span",[t._v(t._s(t.$t("dbList.shujuku-liebiao")))])])],1)],1),a("el-col",{staticClass:"warp-main",staticStyle:{"box-shadow":"1px 1px 5px #eee"},attrs:{span:24}},[a("el-form",{staticClass:"demo-form-inline",staticStyle:{display:"inline-block"},attrs:{inline:!0,model:t.filters},nativeOn:{submit:function(t){t.preventDefault()}}},[a("el-form-item",[a("el-input",{staticStyle:{width:"400px"},attrs:{placeholder:t.$t("dbList.qingshuru-shujuku-mingcheng-ip")},nativeOn:{keyup:function(e){return!e.type.indexOf("key")&&t._k(e.keyCode,"enter",13,e.key,"Enter")?null:t.handleSearch(e)}},model:{value:t.filters.name,callback:function(e){t.$set(t.filters,"name",e)},expression:"filters.name "}},[a("el-button",{attrs:{slot:"append",type:"primary"},on:{click:t.handleSearch},slot:"append"},[t._v(t._s(t.$t("dbList.shou-suo")))])],1),a("el-tooltip",{staticClass:"item",attrs:{effect:"dark",content:t.$t("Public.question"),placement:"top"}},[a("i",{staticClass:"el-icon-question",staticStyle:{"margin-left":"5px"}})])],1)],1),a("div",{staticStyle:{float:"right","margin-top":"6px"}},[a("el-popover",{attrs:{placement:"right",title:t.$t("dbList.xuanze-xuyao-xianshi-delie"),trigger:"click",width:"155"}},[a("el-checkbox-group",{staticStyle:{overflow:"hidden"},attrs:{size:"mini"},model:{value:t.checkedColumns,callback:function(e){t.checkedColumns=e},expression:"checkedColumns"}},[t._l(t.checkBoxGroup,(function(e){return a("el-checkbox",{key:e,staticStyle:{float:"left"},attrs:{value:e,label:e}},[t._v(t._s(t.recleI18nFunc(e)))])})),a("div",{staticStyle:{float:"left","margin-top":"10px"}},[a("el-button",{attrs:{size:"small",type:"text"},on:{click:function(e){return t.filterFunHandle("allchecked")}}},[t._v(t._s(t.$t("dbList.quan-xuan")))]),a("el-button",{attrs:{size:"small",type:"text"},on:{click:function(e){return t.filterFunHandle("cancel")}}},[t._v(t._s(t.$t("dbList.quxiao-quanxuan")))])],1)],2),a("el-button",{attrs:{slot:"reference",type:"primary",size:"small",plain:""},slot:"reference"},[a("i",{staticClass:"el-icon-arrow-down el-icon-menu"}),t._v(t._s(t.$t("dbList.shai-xuan")))])],1),a("el-dropdown",{staticStyle:{margin:"0 10px"},on:{command:t.createDbDialog}},[a("el-button",{staticClass:"create",attrs:{type:"primary"}},[t._v(" "+t._s(t.$t("dbList.chuangjian-shujuku"))),a("i",{staticClass:"el-icon-arrow-down el-icon--right"})]),a("el-dropdown-menu",{attrs:{slot:"dropdown"},slot:"dropdown"},[t._l(t.dbShowList,(function(e,s){return[e.isShow?a("el-dropdown-item",{key:s,attrs:{command:e.type}},[t._v(t._s(t.recleI18nFunc(e.label2)))]):t._e()]}))],2)],1)],1),a("el-table",{directives:[{name:"loading",rawName:"v-loading",value:t.loading,expression:"loading"}],staticStyle:{width:"100%"},attrs:{data:t.rows,border:"","row-class-name":t.tableRowClassName,"element-loading-text":t.$t("Public.ping-ming-jia-zai-zhong")}},[t.colData[0].istrue?a("el-table-column",{attrs:{fixed:"",prop:"db_id",label:t.$t("dbList.shu-ju-ku"),align:"center","min-width":"80px"}}):t._e(),t.colData[1].istrue?a("el-table-column",{attrs:{fixed:"",prop:"up_db_id",label:t.$t("dbList.shang-ji-ku"),align:"center","min-width":"130px"},scopedSlots:t._u([{key:"default",fn:function(e){return[2!==e.row.state?a("span",{staticStyle:{cursor:"pointer"},on:{click:function(a){return t.handleSearchByUpper(e.row.up_db_id)}}},[t._v(" "+t._s(e.row.up_db_id)+" ")]):t._e(),2!=e.row.state||e.row.cluster_id?t._e():a("span",{staticStyle:{cursor:"pointer"},on:{click:function(a){return t.handleSearchByUpper(e.row.up_db_id)}}},[t._v(" "+t._s(e.row.up_db_id)+" ")]),2==e.row.state&&e.row.cluster_id?a("del",{staticStyle:{"text-decoration":"line-through",color:"#000"}},[a("span",{staticStyle:{color:"#9a9a9a",cursor:"pointer"},on:{click:function(a){return t.handleSearchByUpper(e.row.up_db_id)}}},[t._v(" "+t._s(e.row.up_db_id)+" ")])]):t._e()]}}],null,!1,1721830667)}):t._e(),t.colData[2].istrue?a("el-table-column",{attrs:{fixed:"",label:t.$t("dbList.jiqun-id"),align:"center",width:"75px"},scopedSlots:t._u([{key:"default",fn:function(e){return[a("span",{staticStyle:{cursor:"pointer"},on:{click:function(a){return t.openClusterDialog(e.row)}}},[t._v(" "+t._s(e.row.cluster_id)+" ")])]}}],null,!1,2658784215)}):t._e(),t.colData[3].istrue?a("el-table-column",{attrs:{"header-row-class-name":"csclass",prop:"db_state",label:t.$t("dbList.zhuang-tai"),align:"center","min-width":"115px"},scopedSlots:t._u([{key:"default",fn:function(e){return[3===e.row.db_state?a("span",[a("i",{staticClass:"el-icon-loading"}),a("span",{staticClass:"statefont"},[t._v(" "+t._s(t.$t("dbList.hui-fu-zhong")))])]):t._e(),2===e.row.db_state?a("span",[a("i",{staticClass:"el-icon-loading"}),a("span",{staticClass:"statefont"},[t._v(" "+t._s(t.$t("dbList.chuang-jian-zhong")))])]):t._e(),0===e.row.db_state?a("i",{staticClass:"el-icon-success green"},[a("span",{staticClass:"statefont"},[t._v(" "+t._s(t.$t("dbList.yun-xing-zhong")))])]):1===e.row.db_state?a("i",{staticClass:"el-icon-info"},[a("span",{staticClass:"statefont"},[t._v(" "+t._s(t.$t("dbList.ting-zhi")))])]):-1===e.row.db_state?a("i",{staticClass:"el-icon-warning orange"},[a("span",{staticClass:"statefont"},[t._v(" "+t._s(t.$t("dbList.agent-yichang")))])]):4===e.row.db_state?a("i",{staticClass:"el-icon-info red"},[a("span",{staticClass:"statefont"},[t._v(" "+t._s(t.$t("dbLists.chuangjian-shibai")))])]):t._e()]}}],null,!1,3217219888)}):t._e(),t.colData[4].istrue?a("el-table-column",{attrs:{prop:"instance_name",label:t.$t("dbList.shujuku-mingcheng"),align:"center",width:"120px","show-overflow-tooltip":""}}):t._e(),t.colData[8].istrue?a("el-table-column",{attrs:{prop:"room_name",label:t.$t("dbList.jifang-mingcheng"),align:"center","min-width":"135px","show-overflow-tooltip":""},scopedSlots:t._u([{key:"default",fn:function(e){return[a("span",{staticClass:"statefont"},[t._v(" "+t._s(null!=e.row.cluster_id&&null==e.row.room_name||"默认机房"==e.row.room_name?t.$t("dbList.moren-jifang"):e.row.room_name))])]}}],null,!1,2835797268)}):t._e(),t.colData[7].istrue?a("el-table-column",{attrs:{prop:"host",label:t.$t("dbList.suozai-zhuji"),align:"center","min-width":"130px","show-overflow-tooltip":""},scopedSlots:t._u([{key:"default",fn:function(e){return[a("el-dropdown",{attrs:{trigger:"click"},on:{command:t.funChandleClick}},[a("span",{staticClass:"el-dropdown-link",staticStyle:{color:"#0070cc","font-weight":"500"}},[t._v(" "+t._s(e.row.host)),a("i",{staticClass:"el-icon-arrow-down el-icon--right"})]),a("el-dropdown-menu",{attrs:{slot:"dropdown"},slot:"dropdown"},[a("el-dropdown-item",{staticClass:"session",attrs:{command:t.composeValue("conversation",e.$index,e.row)}},[t._v(t._s(t.$t("dbList.huihua-jiankong")))]),a("el-dropdown-item",{staticClass:"lock",attrs:{command:t.composeValue("lock",e.$index,e.row)}},[t._v(t._s(t.$t("dbList.suo-guan-li")))])],1)],1)]}}],null,!1,1048657923)}):t._e(),t.colData[5].istrue?a("el-table-column",{attrs:{prop:"version",label:t.$t("licManager.ban-ben"),align:"center",width:"80px","show-overflow-tooltip":""}}):t._e(),t.colData[9].istrue?a("el-table-column",{attrs:{prop:"port",label:t.$t("dashboard.duan-kou"),align:"center","min-width":"80px"}}):t._e(),t.colData[10].istrue?a("el-table-column",{attrs:{prop:"pgdata",label:t.$t("dbList.shujuku-mulu"),align:"center","min-width":"150px","show-overflow-tooltip":""}}):t._e(),t.colData[6].istrue?a("el-table-column",{attrs:{prop:"instance_type",label:t.$t("dbList.shujuku-leixing"),align:"center","min-width":"110px"},scopedSlots:t._u([{key:"default",fn:function(e){return[a("span",{staticClass:"statefont"},[t._v(" "+t._s(11==e.row.db_type?"polardb":t.pgTypeText))])]}}],null,!1,1529229695)}):t._e(),t.colData[11].istrue?a("el-table-column",{attrs:{fixed:"right",prop:"is_primary",label:t.$t("dbList.zhu-bei-ku"),align:"center","min-width":"125px"},scopedSlots:t._u([{key:"default",fn:function(e){return[a("span",{staticClass:"statefont"},[t._v(" "+t._s(1===e.row.is_primary&&2!==e.row.state?t.$t("dbList.zhu-ku"):0===e.row.is_primary&&2!==e.row.state?t.$t("dbList.bei-ku"):""))]),a("span",{staticClass:"statefont"},[t._v(t._s(1!==e.row.is_primary||2!=e.row.state||e.row.cluster_id?0!==e.row.is_primary||2!=e.row.state||e.row.cluster_id?"":t.$t("dbList.bei-ku"):t.$t("dbList.zhu-ku")))]),a("del",{staticStyle:{"text-decoration":"line-through",color:"#000"}},[a("span",{staticStyle:{color:"#9a9a9a"}},[t._v(t._s(1===e.row.is_primary&&2==e.row.state&&e.row.cluster_id?t.$t("dbList.zhu-ku"):0===e.row.is_primary&&2==e.row.state&&e.row.cluster_id?t.$t("dbList.bei-ku"):""))])])]}}],null,!1,227444075)}):t._e(),a("el-table-column",{attrs:{fixed:"right",prop:"handle",label:t.$t("dbList.cao-zuo"),align:"center","min-width":"150px"},scopedSlots:t._u([{key:"default",fn:function(e){return[a("el-link",{directives:[{name:"show",rawName:"v-show",value:1===e.row.db_state,expression:"scope.row.db_state === 1"}],staticClass:"normal start",on:{click:function(a){return t.startSubmit(e.$index,e.row)}}},[t._v(t._s(t.$t("dbList.qi-dong")))]),a("el-link",{directives:[{name:"show",rawName:"v-show",value:0===e.row.db_state,expression:"scope.row.db_state === 0"}],staticClass:"normal stop",on:{click:function(a){return t.stopSubmit(e.$index,e.row)}}},[t._v(t._s(t.$t("dbList.ting-zhi")))]),a("span",{directives:[{name:"show",rawName:"v-show",value:1===e.row.db_state||0===e.row.db_state,expression:"scope.row.db_state === 1||scope.row.db_state === 0"}],staticStyle:{color:"rgb(218 220 224)","font-size":"12px","margin-right":"6px"}},[t._v("|")]),a("el-dropdown",{attrs:{trigger:"click"},on:{command:t.handleClick}},[a("span",{staticClass:"el-dropdown-link",staticStyle:{color:"#0070cc","font-weight":"500"}},[t._v(" "+t._s(t.$t("dbList.geng-duo"))),a("i",{staticClass:"el-icon-arrow-down el-icon--right"})]),a("el-dropdown-menu",{attrs:{slot:"dropdown"},slot:"dropdown"},[a("el-dropdown-item",{staticClass:"edit",attrs:{disabled:4===e.row.db_state,command:t.composeValue("1",e.$index,e.row)},on:{click:function(a){return t.editDBFn(e.$index,e.row)}}},[t._v(t._s(t.$t("dbList.bian-ji")))]),a("el-tooltip",{staticClass:"item",attrs:{"open-delay":1e3,disabled:0!==e.row.db_state,effect:"dark",content:t.$t("dbList.toolTip-del"),placement:"top"}},[a("div",{staticClass:"del"},[a("el-dropdown-item",{attrs:{command:t.composeValue("2",e.$index,e.row),disabled:0===e.row.db_state}},[t._v(t._s(t.$t("dbList.shan-chu")))])],1)]),0===e.row.alarm?a("el-dropdown-item",{attrs:{command:t.composeValue("3",e.$index,e.row)}},[t._v(t._s(t.$t("dbList.tianjian-baojing-dingyi")))]):t._e(),a("el-tooltip",{staticClass:"item",attrs:{"open-delay":1e3,disabled:0===e.row.db_state,effect:"dark",content:t.$t("dbList.toolTip-chongqi"),placement:"top"}},[a("div",{staticClass:"restart"},[a("el-dropdown-item",{attrs:{command:t.composeValue("4",e.$index,e.row),disabled:0!==e.row.db_state}},[t._v(t._s(t.$t("dbList.chong-qi")))])],1)]),a("el-tooltip",{staticClass:"item",attrs:{"open-delay":1e3,disabled:0===e.row.db_state,effect:"dark",content:t.$t("dbList.toolTip-dabeiku"),placement:"top"}},[a("div",{staticClass:"standby"},[a("el-dropdown-item",{attrs:{command:t.composeValue("7",e.$index,e.row),disabled:0!==e.row.db_state}},[t._v(t._s(t.$t("dbList.da-bei-ku")))])],1)]),a("el-tooltip",{staticClass:"item ",attrs:{"open-delay":1e3,effect:"dark",content:0===e.row.db_state&&1==e.row.switch?t.$t("dbList.qiehuan-shangyiji-de-zhuku"):t.$t("dbList.meiyou-keyi-qiehuan-message"),placement:"top"}},[a("div",{staticClass:"switch"},[a("el-dropdown-item",{attrs:{command:t.composeValue("8",e.$index,e.row),disabled:0!==e.row.db_state||1!=e.row.switch}},[t._v(" "+t._s(t.$t("dbList.qiehuan-shangjiku"))+" ")])],1)]),a("el-tooltip",{staticClass:"item",attrs:{"open-delay":1e3,effect:"dark",content:0===e.row.db_state&&0==e.row.is_primary?t.$t("dbList.beiku-jihuo-message"):t.$t("dbList.shujuku-bushi-message"),placement:"top"}},[a("div",{staticClass:"active"},["reader"!==e.row.polar_type&&"standby"!==e.row.polar_type?a("el-dropdown-item",{attrs:{command:t.composeValue("9",e.$index,e.row),disabled:0!==e.row.db_state||0!==e.row.is_primary}},[t._v(" "+t._s(t.$t("dbList.ji-huo"))+" ")]):t._e()],1)]),a("div",{staticClass:"change"},[a("el-tooltip",{staticClass:"item",attrs:{disabled:!(0!==e.row.db_state&&1!==e.row.db_state||e.row.major_version<=9),"open-delay":1e3,effect:"dark",content:t.$t("dbList.jinzhichi-m"),placement:"top"}},[a("div",[a("el-dropdown-item",{attrs:{disabled:0!==e.row.db_state&&1!==e.row.db_state||e.row.major_version<=9,command:t.composeValue("11",e.$index,e.row)}},[t._v(" "+t._s(t.$t("dbList.xiugai-shujuku-peizhi"))+" ")])],1)])],1),a("el-tooltip",{staticClass:"item",attrs:{"open-delay":1e3,disabled:"master"===e.row.polar_type&&0===e.row.db_state,effect:"dark",content:t.$t("dbList.polarDB-gongxiangcunchu-m"),placement:"top"}},[a("div",{staticClass:"dilatation"},[11==e.row.db_type?a("el-dropdown-item",{attrs:{disabled:"master"!==e.row.polar_type||0!==e.row.db_state,command:t.composeValue("12",e.$index,e.row)}},[t._v(" "+t._s(t.$t("dbList.pfs-kuorong"))+" ")]):t._e()],1)]),a("div",[a("el-dropdown-item",{attrs:{disabled:0!==e.row.db_state&&1!==e.row.db_state,command:t.composeValue("13",e.$index,e.row)}},[t._v(" "+t._s(t.$t("viewDatabaseLogs.chakanshujuku-rizhi"))+" ")])],1)],1)],1)]}}])})],1),a("div",{staticClass:"block",staticStyle:{overflow:"hidden"}},[a("div",{staticStyle:{float:"right"}},[a("el-pagination",{ref:"pagination",attrs:{layout:"total, sizes, prev, pager, next, jumper",total:t.total,"page-sizes":[20,30,40,50,100]},on:{"size-change":t.handleSizeChange,"current-change":t.handleCurrentChange}})],1)]),t.dataBaseShow?a("el-dialog",{staticClass:"makeDialog",attrs:{top:"0",title:t.$t("dbList.dajian-beiku"),"append-to-body":!0,visible:t.dataBaseShow,"close-on-click-modal":!1,width:"80%"},on:{"update:visible":function(e){t.dataBaseShow=e}}},[t.dataBaseShow?a("standby-Page",{attrs:{"database-id":t.databaseId,"database-info":t.databaseInfo,"databaselist-data":t.rows},on:{"open-task":t.openTaskDialog,"refresh-form":t.formloding,"down-form":t.formlodingDown,"close-form":t.closePopup}}):t._e()],1):t._e(),a("el-dialog",{attrs:{"append-to-body":!0,visible:t.switchDataBaseShow,top:"30vh",width:"60%"},on:{"update:visible":function(e){t.switchDataBaseShow=e}}},[a("div",{attrs:{slot:"title"},slot:"title"},[a("span",{staticClass:"el-dialog__title"},[t._v(t._s(t.$t("dbList.xuanze-shangjiku")))]),a("el-tooltip",{staticClass:"item",attrs:{"open-delay":1e3,effect:"dark",placement:"top-start"}},[a("div",{attrs:{slot:"content"},slot:"content"},[t._v(" "+t._s(t.$t("dbList.questionMessageOneLine"))+" "),a("br"),a("br"),t._v(" "+t._s(t.$t("dbList.questionMessageTwoLine"))+" "),a("br"),a("br"),t._v(" "+t._s(t.$t("dbList.questionMessageThreeLine"))+" ")]),a("i",{staticClass:"el-icon-question",staticStyle:{"margin-left":"5px"}})])],1),t.switchDataBaseShow?a("switch-Page",{attrs:{"database-data":t.databaseData},on:{"refresh-form":t.formloding,"down-form":t.formlodingDown,"close-form":t.closePopup}}):t._e()],1),t.pfsDilatationShow?a("el-dialog",{staticClass:"makeDialog",attrs:{top:"-10vh",title:t.$t("dbList.pfs-kuorong"),"append-to-body":!0,visible:t.pfsDilatationShow,"close-on-click-modal":!1},on:{"update:visible":function(e){t.pfsDilatationShow=e}}},[t.pfsDilatationShow?a("pfsDilatation",{attrs:{"database-data":t.databaseData},on:{"open-task":t.openTaskDialog,"close-form":t.closePopup}}):t._e()],1):t._e(),a("el-dialog",{attrs:{"append-to-body":!0,visible:t.createPostgresDatabaseShow,"close-on-click-modal":!1,width:"80%"},on:{"update:visible":function(e){t.createPostgresDatabaseShow=e}}},[a("div",{attrs:{slot:"title"},slot:"title"},[a("span",{staticClass:"el-dialog__title"},[t._v(t._s(t.$t("dbList.chuangjian-shujuku")))]),a("el-tooltip",{staticClass:"item",attrs:{"open-delay":1e3,effect:"dark",content:t.$t("dbList.tongguo-chengxu-message")+t.pgTypeText+t.$t("dbList.yong-hu"),placement:"top"}},[a("i",{staticClass:"el-icon-question",staticStyle:{"margin-left":"5px"}})])],1),t.createPostgresDatabaseShow?a("createPostgresDatabase",{attrs:{"databaselist-data":t.rows,"create-type":t.createType},on:{"open-task":t.openTaskDialog,"refresh-form":t.formloding,"down-form":t.formlodingDown,"close-form":t.closePopup}}):t._e()],1),a("el-dialog",{attrs:{"append-to-body":!0,visible:t.createPolarDBDatabaseShow,"close-on-click-modal":!1,width:"80%"},on:{"update:visible":function(e){t.createPolarDBDatabaseShow=e}}},[a("div",{attrs:{slot:"title"},slot:"title"},[a("span",{staticClass:"el-dialog__title"},[t._v(t._s(t.$t("dbList.chuangjian-shujuku")))]),a("el-tooltip",{staticClass:"item",attrs:{"open-delay":1e3,effect:"dark",content:t.$t("dbList.tongguo-chengxu-chuangjian-polardb-m",[t.pgTypeText]),placement:"top"}},[a("i",{staticClass:"el-icon-question",staticStyle:{"margin-left":"5px"}})])],1),t.createPolarDBDatabaseShow?a("createPolarDBDatabase",{attrs:{"databaselist-data":t.rows,"create-type":t.createType},on:{"open-task":t.openTaskDialog,"refresh-form":t.formloding,"down-form":t.formlodingDown,"close-form":t.closePopup}}):t._e()],1),a("task-log",{ref:"tasklog",on:{"close-refresh":t.getDBList}}),a("editmsg-Tab",{ref:"editmsgTab",on:{"close-form":t.closePopup}}),a("editconfig-Tab",{ref:"editconfigTab",on:{"close-form":t.closePopup}}),a("viewDatabaseLogs",{ref:"viewDatabaseLogs",on:{"close-form":t.closePopup}})],1),a("oper-cluster",{ref:"OperCluster",on:{refreshTable:t.getDBList}})],1)}),[],!1,u,"4368e0da",null,null);function u(t){for(let e in c)this[e]=c[e]}var h=function(){return p.exports}();export{h as default};