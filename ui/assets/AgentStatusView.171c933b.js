import{P as t}from"./index.dfdb83b1.js";import e from"./taskLog.9e8d66b5.js";import{n as a}from"./index.c66ec47f.js";import"./vendor.194c4086.js";import"./bus.d56574c1.js";var i=e=>t("/api/v1/get_host_list",e),n=e=>t("/api/v1/add_alarm",e),s=e=>t("/api/v1/remove_host",e);const l={};var o=a({name:"AgentStatusView",data:()=>({filters:{name:"",state:""},total:0,page:1,size:20,loading:!1,rows:[],agentCheck:"",restart_agent:!1,editProp:["tar_path","upload_path"],clickCellMap:{},needToFirstPage:!1,clupServerLoading:!1}),components:{taskLog:e},watch:{"filters.name"(t,e){t!=e&&""!=t&&(this.needToFirstPage=!0)}},methods:{tableRowClassName:({row:t,rowIndex:e})=>e%2!=0?"warning-row":"success-row",checkboxChange(){this.needToFirstPage=!0,this.showList()},handleSizeChange(t){this.size=t,this.needToFirstPage=!0,this.showList()},handleCurrentChange(t){this.page=t,this.showList()},handleSearch(){this.showList()},showList:function(){let t=this;this.needToFirstPage&&(this.page=1),1==this.page&&(this.total=0);let e={page_size:t.size,page_num:t.page};""!==t.filters.name&&(e.filter=t.filters.name),""!==t.filters.state&&(e.state=Number(t.filters.state)),t.loading=!0,i(e).then((function(e){t.loading=!1,t.needToFirstPage=!1,e&&e.rows&&(t.total=e.total,t.rows=e.rows),t.$nextTick((()=>{t.$emit("btnHidden")}))}),(function(e){t.loading=!1}))},addAlarmDefinition:function(t,e){let a=this;this.$confirm(this.$t("dbList.gaishujuku-message")+e.hid+this.$t("dbList.haimeiyou-tianjia-message"),this.$t("index.ti-shi"),{type:"warning",closeOnClickModal:!1}).then((()=>{a.loading=!0;let t={object_id:e.hid,obj_type:"host"};n(t).then((function(){a.loading=!1,a.showList()}),(function(t){a.loading=!1}))})).catch((()=>{}))},removeHost:function(t,e){let a=this;this.$confirm(this.$t("AgentStatusView.shifou-queren-jiang-m")+e.hid+this.$t("AgentStatusView.xiaxian"),this.$t("index.ti-shi"),{type:"warning",closeOnClickModal:!1}).then((()=>{a.loading=!0;let t={ip:e.ip};s(t).then((function(){a.loading=!1;let t=Math.ceil((a.total-1)/a.size),e=a.page>t?t:a.page;a.page=e<1?1:e,a.showList()}),(function(t){a.loading=!1}))}))},gotoLog:function(t){that.$refs.tasklog.openDialog(t,"",1)}},mounted:function(){this.showList()}},(function(){var t=this,e=t.$createElement,a=t._self._c||e;return a("el-row",{staticClass:"warp"},[a("el-col",{staticClass:"warp-breadcrum",attrs:{span:24}},[a("el-breadcrumb",{attrs:{separator:"/"}},[a("el-breadcrumb-item",{attrs:{to:{path:"/AgentStatusView"}}},[a("span",[t._v(t._s(t.$t("AgentStatusView.Agent-xinxi")))])])],1)],1),a("task-log",{ref:"tasklog"}),a("el-col",{staticClass:"warp-main",attrs:{span:24}},[a("el-form",{staticClass:"demo-form-inline",staticStyle:{display:"inline-block"},attrs:{inline:!0,model:t.filters},nativeOn:{submit:function(t){t.preventDefault()}}},[a("el-form-item",[a("el-select",{staticStyle:{width:"100px"},attrs:{placeholder:t.$t("BackupPlanManage.beifen-zhuangtai")},on:{change:t.checkboxChange},model:{value:t.filters.state,callback:function(e){t.$set(t.filters,"state",e)},expression:"filters.state"}},[a("el-option",{attrs:{label:t.$t("BackupPlanManage.quanbu"),value:""}}),a("el-option",{attrs:{label:"Down",value:"-1"}})],1)],1),a("el-form-item",[a("el-input",{staticStyle:{width:"400px","margin-top":"6px"},attrs:{placeholder:t.$t("AgentStatusView.qingshuru-zhuji-mingcheng-m")},nativeOn:{keyup:function(e){return!e.type.indexOf("key")&&t._k(e.keyCode,"enter",13,e.key,"Enter")?null:t.handleSearch(e)}},model:{value:t.filters.name,callback:function(e){t.$set(t.filters,"name",e)},expression:"filters.name "}},[a("el-button",{attrs:{slot:"append",type:"primary"},on:{click:t.handleSearch},slot:"append"},[t._v(t._s(t.$t("dbList.shou-suo")))])],1),a("el-tooltip",{staticClass:"item",attrs:{effect:"dark",content:t.$t("Public.question"),placement:"top"}},[a("i",{staticClass:"el-icon-question",staticStyle:{"margin-left":"5px"}})])],1)],1),a("div",{attrs:{align:"right"}},[a("el-button",{attrs:{type:"primary",size:"medium"},on:{click:function(e){return t.showList()}}},[t._v(t._s(t.$t("resourceManagement.shua-xin")))])],1),a("el-table",{directives:[{name:"loading",rawName:"v-loading",value:t.loading,expression:"loading"}],staticStyle:{width:"100%"},attrs:{"row-class-name":t.tableRowClassName,data:t.rows,border:"","element-loading-text":t.$t("Public.ping-ming-jia-zai-zhong")}},[a("el-table-column",{attrs:{prop:"state",label:t.$t("AgentStatusView.Agent-zhuangtai"),align:"center","header-align":"center",width:"120px"},scopedSlots:t._u([{key:"default",fn:function(e){return[1===e.row.state?a("i",{staticClass:"el-icon-success green"},[a("span",{staticClass:"statefont"},[t._v(" UP")])]):t._e(),-1===e.row.state?a("i",{staticClass:"el-icon-error red"},[a("span",{staticClass:"statefont"},[t._v(" Down")])]):t._e()]}}])}),a("el-table-column",{attrs:{prop:"ip",label:t.$t("AgentStatusView.IP-dizhi"),align:"center","min-width":"130px"}}),a("el-table-column",{attrs:{prop:"hostname",label:t.$t("AgentStatusView.zhuji-ming"),align:t.$t("AgentStatusView.cenAgent-jiqi-rizhi-m"),"min-width":"100px","show-overflow-tooltip":""}}),a("el-table-column",{attrs:{prop:"os",label:t.$t("AgentStatusView.caozuo-xitong"),align:"center","min-width":"100px"}}),a("el-table-column",{attrs:{prop:"cpu_cores",label:t.$t("createDatabasePage.CPU-heshu"),align:"center","min-width":"100px"}}),a("el-table-column",{attrs:{prop:"version",label:"Agent "+t.$t("licManager.ban-ben"),align:"center","min-width":"100px"}}),a("el-table-column",{attrs:{prop:"handle",label:t.$t("dbList.cao-zuo"),align:"center","min-width":"100px"},scopedSlots:t._u([{key:"default",fn:function(e){return[0===e.row.is_alarm?a("el-link",{attrs:{size:"mini"},on:{click:function(a){return t.addAlarmDefinition(e.$index,e.row)}}},[t._v(t._s(t.$t("dbList.tianjian-baojing-dingyi")))]):t._e(),-1===e.row.state?a("el-link",{staticClass:"offLine",attrs:{size:"mini"},on:{click:function(a){return t.removeHost(e.$index,e.row)}}},[t._v(t._s(t.$t("AgentStatusView.jiqi-xiaxian")))]):t._e()]}}])})],1),a("div",{staticClass:"block",staticStyle:{float:"right"}},[a("el-pagination",{ref:"pagination",attrs:{layout:"total, sizes, prev, pager, next, jumper",total:t.total,"page-sizes":[20,30,40,50,100]},on:{"size-change":t.handleSizeChange,"current-change":t.handleCurrentChange}})],1)],1)],1)}),[],!1,r,"1c558c3c",null,null);function r(t){for(let e in l)this[e]=l[e]}var c=function(){return o.exports}();export{c as default};
