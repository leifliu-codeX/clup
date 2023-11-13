import{A as e}from"./api_publicComponent.c4201f33.js";import t from"./taskLog.8883e917.js";import{n as i}from"./index.e6909a03.js";import"./index.dfdb83b1.js";import"./vendor.194c4086.js";import"./bus.d56574c1.js";const s={};var a=i({name:"logInformation",inject:["reload"],components:{taskLog:t},props:{namecs:{required:!1}},data(){return{logtype:1,clusterList:[],filters:{stateSearch:"",typeSearch:"",taskName:"",taskBeginTime:"",taskEndTime:"",cluster_id:""},total:0,page:1,size:20,loading:!1,rows:[],taskTypeList:["ALL"],taskId:"",taskDetail:"",showTaskDetailVisible:!1,content:"",intervalID:"",needToFirstPage:!1,isTableshow:!0,startTime:{disabledDate:e=>{if(this.filters.taskEndTime)return e.getTime()>new Date(this.filters.taskEndTime).getTime()}},endTime:{disabledDate:e=>{if(this.filters.taskBeginTime)return e.getTime()<new Date(this.filters.taskBeginTime).getTime()}}}},watch:{$route:"fetchData","filters.searchKey"(e,t){e!=t&&""!=e&&(this.needToFirstPage=!0)},"filters.typeSearch"(e,t){e!=t&&""!=e&&(this.needToFirstPage=!0)},"filters.taskName"(e,t){e!=t&&""!=e&&(this.needToFirstPage=!0)},"filters.taskBeginTime"(e,t){e!=t&&""!=e&&(this.needToFirstPage=!0)},"filters.taskEndTime"(e,t){e!=t&&""!=e&&(this.needToFirstPage=!0)}},methods:{checkboxChange(){this.needToFirstPage=!0,this.showList()},fetchData(e,t){console.log(t),console.log(e),this.$refs.pagination.internalCurrentPage=1,this.logtype=e.query.logtype,this.InitializationList()},handleSizeChange(e){this.size=e,this.total=0,this.needToFirstPage=!0,this.showList()},handleCurrentChange(e){this.page=e,this.showList()},handleSearch(){this.showList()},getTaskTypeList:function(){let t=this,i={task_class:this.logtype};t.loading=!0,e.getCbuTaskTypeList(i).then((function(e){t.loading=!1,t.taskTypeList=e,t.taskTypeList.unshift("ALL")}),(function(e){t.loading=!1}))},showList:function(){let t=this;this.needToFirstPage&&(this.page=1),1==this.page&&(this.total=0);let i={page_size:t.size,task_class:Number(t.logtype),page_num:t.page};""!==t.filters.stateSearch&&(i.state=t.filters.stateSearch),""!==t.filters.typeSearch&&(i.task_type=t.filters.typeSearch),t.filters.searchKey&&(i.search_key=t.filters.searchKey),t.filters.taskBeginTime&&(i.begin_create_time=t.filters.taskBeginTime),t.filters.taskEndTime&&(i.end_create_time=t.filters.taskEndTime),t.filters.cluster_id&&(i.cluster_id=t.filters.cluster_id),t.loading=!0,e.getTaskList(i).then((function(e){t.needToFirstPage=!1,t.loading=!1,e&&e.rows&&(t.total=e.total,t.rows=e.rows,t.isTableshow=!1,t.$nextTick((()=>{t.isTableshow=!0,t.$nextTick((()=>{t.$emit("btnHidden")}))})))}),(function(e){t.loading=!1}))},TaskDetailDialog:function(e,t){this.$nextTick((function(){this.$refs.tasklog.openDialog(t.task_id,"",1)}))},InitializationList(){const t=this;if(3!=t.logtype)t.getTaskTypeList(),t.loading=!0;else{t.taskTypeList=["ALL","failback","switch","failover","create_sr_cluster"],t.getTaskTypeList();const i={page_num:1,page_size:2e4};e.getClusterList(i).then((function(e){t.loading=!1,e&&e.rows&&(t.clusterList=e.rows,t.showList())}),(function(e){t.loading=!1}))}this.$nextTick(this.showList)}},mounted:function(){this.logtype=this.$route.query.logtype,this.InitializationList(),this.filters={stateSearch:"",typeSearch:"",taskName:"",taskBeginTime:"",taskEndTime:"",cluster_id:""}}},(function(){var e=this,t=e.$createElement,i=e._self._c||t;return i("el-row",[i("el-col",{attrs:{span:24}},[i("el-form",{staticClass:"demo-form-inline",staticStyle:{margin:"0"},attrs:{inline:!0,model:e.filters},nativeOn:{submit:function(e){e.preventDefault()}}},[i("el-form-item",{attrs:{label:e.$t("publicLogComponent.zhuang-tai")}},[i("el-select",{staticStyle:{width:"100px"},attrs:{placeholder:e.$t("publicLogComponent.zhuangtai-xuanze")},on:{change:e.checkboxChange},model:{value:e.filters.stateSearch,callback:function(t){e.$set(e.filters,"stateSearch",t)},expression:"filters.stateSearch"}},[i("el-option",{attrs:{label:"ALL",value:""}}),i("el-option",{attrs:{label:"Success",value:"1"}}),i("el-option",{attrs:{label:"Running",value:"0"}}),i("el-option",{attrs:{label:"Fault",value:"-1"}})],1)],1),i("el-form-item",{attrs:{label:e.$t("publicLogComponent.renwu-leixing")}},[i("el-select",{staticStyle:{width:"100px"},attrs:{placeholder:e.$t("publicLogComponent.renwuleixing-xuanze")},on:{change:e.checkboxChange},model:{value:e.filters.typeSearch,callback:function(t){e.$set(e.filters,"typeSearch",t)},expression:"filters.typeSearch"}},e._l(e.taskTypeList,(function(e,t){return i("el-option",{key:t,attrs:{label:e,value:"ALL"==e?"":e}})})),1)],1),3==e.logtype?i("el-form-item",{attrs:{label:e.$t("publicLogComponent.suoshu-jiqun")}},[i("el-select",{staticStyle:{width:"100px"},attrs:{placeholder:e.$t("publicLogComponent.jiqun-xuanze")},on:{change:e.checkboxChange},model:{value:e.filters.cluster_id,callback:function(t){e.$set(e.filters,"cluster_id",t)},expression:"filters.cluster_id"}},[i("el-option",{attrs:{label:"ALL",value:""}}),e._l(e.clusterList,(function(e,t){return i("el-option",{key:t,attrs:{label:e.cluster_name+"(id="+e.cluster_id+")",value:e.cluster_id}})}))],2)],1):e._e(),i("el-form-item",[i("el-input",{staticStyle:{width:"230px"},attrs:{placeholder:e.$t("publicLogComponent.sousuo-renwu-message")},nativeOn:{keyup:function(t){return!t.type.indexOf("key")&&e._k(t.keyCode,"enter",13,t.key,"Enter")?null:e.handleSearch(t)}},model:{value:e.filters.searchKey,callback:function(t){e.$set(e.filters,"searchKey",t)},expression:"filters.searchKey"}}),i("el-tooltip",{staticClass:"item",attrs:{effect:"dark",content:e.$t("Public.question"),placement:"top"}},[i("i",{staticClass:"el-icon-question",staticStyle:{"margin-left":"5px"}})])],1),i("el-form-item",[i("el-date-picker",{staticStyle:{width:"220px"},attrs:{type:"datetime",placeholder:e.$t("publicLogComponent.qingxuanze-kaishishijian"),"default-time":"","value-format":"yyyy-MM-dd HH:mm:ss","picker-options":e.startTime},model:{value:e.filters.taskBeginTime,callback:function(t){e.$set(e.filters,"taskBeginTime",t)},expression:"filters.taskBeginTime"}})],1),i("el-form-item",[i("el-date-picker",{staticStyle:{width:"220px"},attrs:{type:"datetime",placeholder:e.$t("publicLogComponent.qingxuanze-jieshushijian"),"default-time":"","value-format":"yyyy-MM-dd HH:mm:ss","picker-options":e.endTime},model:{value:e.filters.taskEndTime,callback:function(t){e.$set(e.filters,"taskEndTime",t)},expression:"filters.taskEndTime"}})],1),i("el-form-item",{staticStyle:{float:"right"}},[i("el-button",{attrs:{type:"primary",size:"medium"},on:{click:e.handleSearch}},[e._v(e._s(e.$t("dbList.shou-suo")))])],1)],1)],1),i("el-col",{attrs:{span:24}},[e.isTableshow?i("el-table",{directives:[{name:"loading",rawName:"v-loading",value:e.loading,expression:"loading"}],staticStyle:{width:"100%"},attrs:{data:e.rows,border:"","element-loading-text":e.$t("Public.ping-ming-jia-zai-zhong")}},[i("el-table-column",{attrs:{prop:"task_id",label:e.$t("publicLogComponent.renwu-ID"),align:"center",width:"80px"}}),i("el-table-column",{attrs:{prop:"state",label:e.$t("dbList.zhuang-tai"),"header-align":"center",align:"left",width:"100px"},scopedSlots:e._u([{key:"default",fn:function(t){return[1===t.row.state?i("i",{staticClass:"el-icon-success green"},[i("span",{staticClass:"statefont"},[e._v(" Success")])]):-1===t.row.state?i("i",{staticClass:"el-icon-success red"},[i("span",{staticClass:"statefont"},[e._v(" Fault")])]):0===t.row.state?i("i",{staticClass:"el-icon-success"},[i("span",{staticClass:"statefont"},[e._v(" running")])]):e._e()]}}],null,!1,505972830)}),3==e.logtype?i("el-table-column",{attrs:{prop:"cluster_id",label:e.$t("publicLogComponent.suoshu-jiqun-no"),align:"center",width:"80px"}}):e._e(),i("el-table-column",{attrs:{prop:"task_type",label:e.$t("publicLogComponent.renwu-leixing-no"),"header-align":"center",align:"left",width:"180px"}}),i("el-table-column",{attrs:{prop:"task_name",label:e.$t("publicLogComponent.renwu-mingcheng"),"header-align":"center",align:"left","min-width":"100px","show-overflow-tooltip":""}}),i("el-table-column",{attrs:{prop:"create_time",label:e.$t("dashboard.chuangjian-shijian"),align:"center",width:"160px","show-overflow-tooltip":""}}),i("el-table-column",{attrs:{prop:"last_msg",label:e.$t("dashboard.xin-xi"),align:"center","min-width":"160px"},scopedSlots:e._u([{key:"default",fn:function(t){return[i("el-tooltip",{staticClass:"item",attrs:{effect:"dark",placement:"top"}},[i("div",{staticStyle:{"overflow-y":"auto","white-space":"pre-wrap"},attrs:{slot:"content"},slot:"content"},[i("pre",[e._v(e._s(t.row.last_msg))])]),i("div",{staticStyle:{"white-space":"nowrap",overflow:"hidden","text-overflow":"ellipsis"}},[e._v(e._s(t.row.last_msg))])])]}}],null,!1,3279762957)}),i("el-table-column",{attrs:{prop:"handle",label:e.$t("clusterDefine.caozuo"),align:"center",width:"100px"},scopedSlots:e._u([{key:"default",fn:function(t){return[i("el-button",{staticClass:"normal detail",on:{click:function(i){return e.TaskDetailDialog(t.$index,t.row)}}},[e._v(e._s(e.$t("publicLogComponent.xianshi-xiangqing")))])]}}],null,!1,63140491)})],1):e._e(),i("task-log",{ref:"tasklog"}),i("div",{staticClass:"block",staticStyle:{float:"right"}},[i("el-pagination",{ref:"pagination",attrs:{layout:"total, sizes, prev, pager, next, jumper",total:e.total,"page-sizes":[20,30,40,50,100]},on:{"size-change":e.handleSizeChange,"current-change":e.handleCurrentChange}})],1)],1)],1)}),[],!1,l,"7b4e1c30",null,null);function l(e){for(let t in s)this[t]=s[t]}var n=function(){return a.exports}();export{n as default};