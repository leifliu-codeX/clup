import{A as e}from"./api_dbManage.4e8ccada.js";import{n as t}from"./index.c66ec47f.js";import"./index.dfdb83b1.js";import"./vendor.194c4086.js";import"./bus.d56574c1.js";const o={};var s=t({name:"LockManage",data:()=>({needToFirstPage:!1,sortRule:{prop:null,order:null},tabData:"",loading:!1,total:0,page:1,size:20,oldpage:1,selectValue:"",isLockLoad:!1,tipsText:!1,noData:{},dbHostMsg:{},dbListForLoop:{},sessionRows:[]}),watch:{selectValue:function(e){const t=this;let o={};for(let s=0;s<t.dbListForLoop.length;s++)e==t.dbListForLoop[s].db_id&&(o=t.dbListForLoop[s]);t.isLockLoad?(t.needToFirstPage=!0,t.getDBListFn(o)):t.isLockLoad=!0}},mounted(){null!=this.$route.query.data?this.getDBListFn(this.$route.query.data):this.getDBListFn()},methods:{sortChange(e){const t=this;if(null!=e.order){var o=[];for(let s=0;s<t.sessionRows.length;s++)null===t.sessionRows[s][e.prop]?o.push(t.sessionRows[s]):o.unshift(t.sessionRows[s]);t.sessionRows=o}null==e.order&&(t.sessionRows,t.tabData),t.$nextTick((()=>{t.$emit("btnHidden")})),t.sortChange.order=e.order,t.sortChange.prop=e.prop},tableRowClassName:({row:e,rowIndex:t})=>t%2!=0?"warning-row":"success-row",handleSizeChange(e){this.size=e,this.oldpage=this.page,this.needToFirstPage=!0,this.getSessionList()},handleCurrentChange(e){this.page=e,this.oldpage=this.page,this.getSessionList()},copy(e){this.$message({message:this.$t("SessionManage.yichenggong-fuzhi-message"),type:"success"})},onError(e){this.$message.error(this.$t("SessionManage.fuzhi-dao-jianqie-message"))},getDBListFn(t){const o=this;o.loading=!0,e.getInstanceList().then((function(e){o.loading=!1;let s={};o.dbListForLoop=e.rows,void 0===t?(s=e.rows.find((e=>0===e.db_state)),null!=s?(o.dbHostMsg=s,o.selectValue=o.dbHostMsg.db_id):o.dbHostMsg={}):(null!=o.$route.query.data&&(o.selectValue=o.$route.query.data.db_id),o.dbHostMsg=t),o.dbListForLoop.unshift({db_state:0}),null!=s||(o.tipsText=!0,o.sessionRows=[]),o.getSessionList()}))},getSessionList(){const t=this;t.needToFirstPage&&(t.page=1),1==t.page&&(t.total=0);const o={page_num:t.page,page_size:t.size,db_id:t.dbHostMsg.db_id};t.loading=!0,e.getDbLockInfo(o).then((function(e){t.loading=!1,t.needToFirstPage=!1,t.sessionRows=e.rows,t.tabData=e.rows,null!=t.sortRule.order&&t.sortChange(t.sortRule),t.total=e.total,t.$refs.pagination,t.$nextTick((()=>{t.$emit("btnHidden")}))}),(function(e){t.loading=!1}))},terminationLock(t){let o=this;this.$confirm(this.$t("lockManage.queren-zhongzhi")+t.blocking_pid+this.$t("lockManage.ma"),this.$t("index.ti-shi"),{type:"warning",closeOnClickModal:!1}).then((()=>{o.loading=!0;let s={db_id:o.dbHostMsg.db_id,pid:t.blocking_pid};e.terminateBackend(s).then((function(){o.loading=!1,o.getSessionList()}),(function(e){o.loading=!1}))})).catch((()=>{}))}}},(function(){var e=this,t=e.$createElement,o=e._self._c||t;return o("el-row",{staticClass:"warp"},[o("el-form",[o("el-form-item",[o("el-select",{staticStyle:{width:"170px"},attrs:{filterable:"",placeholder:e.$t("createDatabasePage.qing-xuan-ze")},model:{value:e.selectValue,callback:function(t){e.selectValue=t},expression:"selectValue"}},e._l(e.dbListForLoop,(function(t,s){return o("el-option",{key:s,attrs:{disabled:0!==t.db_state,label:t.db_id?t.host+":"+t.port:e.$t("SessionManage.benji"),value:t.db_id}},[t.db_id?o("el-tooltip",{staticClass:"item",attrs:{"open-delay":1e3,effect:"dark",content:t.host+":"+t.port,placement:"top"}},[t.db_id?o("span",[e._v(" "+e._s(t.host+":"+t.port))]):e._e()]):o("span",[e._v(" "+e._s(e.$t("SessionManage.benji")))])],1)})),1),o("div",{staticStyle:{float:"right"}},[o("el-button",{staticClass:"normal el-icon-refresh-right",on:{click:e.getSessionList}},[e._v(" "+e._s(e.$t("resourceManagement.shua-xin")))])],1)],1)],1),o("el-table",{directives:[{name:"loading",rawName:"v-loading",value:e.loading,expression:"loading"}],staticStyle:{width:"100%"},attrs:{"default-sort":e.sortRule,"row-class-name":e.tableRowClassName,data:e.sessionRows,border:"","element-loading-text":"正在加载中..."},on:{"sort-change":e.sortChange}},[o("el-table-column",{attrs:{prop:"blocking_pid",label:e.$t("lockManage.zuse-pid"),align:"center",width:"90px",fixed:""}}),o("el-table-column",{attrs:{prop:"blocking_user",sortable:"",label:e.$t("lockManage.zuse-yonghu"),align:"center","min-width":"100px","show-overflow-tooltip":""}}),o("el-table-column",{attrs:{prop:"blocking_query",label:e.$t("lockManage.zuse-sql"),align:"center","min-width":"200px","show-overflow-tooltip":""}}),o("el-table-column",{attrs:{prop:"blocked_pid",label:e.$t("lockManage.beizuse-pid"),align:"center"}}),o("el-table-column",{attrs:{prop:"blocked_user","min-width":"120px",sortable:"",label:e.$t("lockManage.beizuse-yonghu"),align:"center","show-overflow-tooltip":""}}),o("el-table-column",{attrs:{prop:"query",label:e.$t("lockManage.beizuse-sql"),align:"center","min-width":"200px","show-overflow-tooltip":""}}),o("el-table-column",{attrs:{prop:"age",sortable:"",label:e.$t("lockManage.beizuse-shijian"),align:"center",width:"120px","show-overflow-tooltip":""}}),o("el-table-column",{attrs:{prop:"detail",label:e.$t("dbList.cao-zuo"),align:"center",width:"120px",fixed:"right"},scopedSlots:e._u([{key:"default",fn:function(t){return[o("el-link",{staticClass:"kill",on:{click:function(o){return e.terminationLock(t.row)}}},[e._v(e._s(e.$t("lockManage.zhongzhisuo")))])]}}])})],1),o("div",{staticClass:"block",staticStyle:{float:"right"}},[o("el-pagination",{ref:"pagination",attrs:{layout:"total, sizes, prev, pager, next, jumper",total:e.total,"page-sizes":[20,30,40,50,100]},on:{"size-change":e.handleSizeChange,"current-change":e.handleCurrentChange}})],1)],1)}),[],!1,a,"724181b5",null,null);function a(e){for(let t in o)this[t]=o[t]}var i=function(){return s.exports}();export{i as default};
