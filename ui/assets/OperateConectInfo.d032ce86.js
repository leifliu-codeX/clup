import{n as e,_ as o}from"./index.8e63218a.js";import{a as n}from"./staticTools.84335405.js";import{A as t}from"./api_clusterManage.8c154fe5.js";import"./vendor.194c4086.js";import"./index.dfdb83b1.js";import"./bus.d56574c1.js";const a={};var i=e({data:()=>({activeName:"",OperateConectInfoVisible:!1,row:null,formInfo:{}}),components:{modifyConnectPooll:()=>o((()=>import("./modifyConnectPooll.a2f1e986.js")),["assets/modifyConnectPooll.a2f1e986.js","assets/modifyConnectPooll.2f36146c.css","assets/api_clusterManage.8c154fe5.js","assets/index.dfdb83b1.js","assets/vendor.194c4086.js","assets/bus.d56574c1.js","assets/staticTools.84335405.js","assets/index.8e63218a.js","assets/index.738ab243.css"])},props:["is-show","data-row"],watch:{activeName:{handler:function(e,o){const{FeMaxConns:a,BeRwConnCount:i,BeRdConnCount:s,FeUser:r,FeDbName:l,FePasswd:c,BeUser:m,BeDbName:d,BePasswd:u,BePortals:f,cluster_id:b}=this.row;switch(e){case"connectCount":this.formInfo=[{name:"fe_max_conns",cname:"FeMaxConns",value:a,type:"number",rules:[{required:!0,message:this.$t("addOrModifyPgHba.qingshuru-neirong",["FeMaxConns"]),trigger:"blur"}]},{name:"be_rw_conns",cname:"BeRwConns",value:i,type:"number",rules:[{required:!0,message:this.$t("addOrModifyPgHba.qingshuru-neirong",["BeRwConns"]),trigger:"blur"},{required:!0,validator:(e,o,n)=>Number(o)<i?n(new Error(this.$t("ConnectionPoolManagement.buneng-xiayu-m",[i]))):n(),trigger:"submit"}]},{name:"be_rd_conns",cname:"BeRdConns",value:s,type:"number",rules:[{required:!0,message:this.$t("addOrModifyPgHba.qingshuru-neirong",["BeRdConns"]),trigger:"blur"},{required:!0,validator:(e,o,n)=>Number(o)<s?n(new Error(this.$t("ConnectionPoolManagement.buneng-xiayu-m",[s]))):n(),trigger:"submit"}]}];break;case"forwardConnectInfo":this.formInfo=[{name:"fe_user",cname:"FeUser",value:r,rules:[this.requiredRules("FeUser")]},{name:"fe_dbname",cname:"FeDBName",value:l,rules:[this.requiredRules("FeDBName")]},{name:"fe_passwd",cname:"FePasswd",value:c,type:"pwd",rules:[this.requiredRules("FePasswd")]}];break;case"backConnectInfo":this.formInfo=[{name:"be_user",cname:"BeUser",value:m,rules:[this.requiredRules("BeUser")]},{name:"be_dbname",cname:"BeDBName",value:d,disabled:!0,rules:[this.requiredRules("BeDBName")]},{name:"be_passwd",cname:"BePasswd",value:u,type:"pwd",rules:[this.requiredRules("BePasswd")]}];break;case"adjustmentNodes":this.formInfo=[];let e={page_size:9999,page_num:1,cluster_id:b};const o=n(".OperateConectInfoDialog .el-dialog");t.getdbList(e).then((e=>{let n=e.rows.map((e=>e.host+":"+String(e.port)));[{name:"portals",cname:this.$t("ConnectionPoolManagement.jiedian-liebiao"),value:f,options:n,type:"selects",rules:[this.requiredRules(this.$t("ConnectionPoolManagement.jiedian-liebiao"),this.$t("ConnectionPoolManagement.qingxuanze-jiedian-liebiao"),"change")]}].forEach(((e,o)=>{this.$set(this.formInfo,o,e)})),o.close()}),(e=>{o.close()}))}}}},methods:{async submit(){const e=n(".OperateConectInfoDialog .el-dialog");try{await this.$refs.modifyConnectPooll.submit(this.activeName),this.$emit("refresh"),this.closeDialog(),e.close()}catch(o){console.error("error"),e.close()}},closeDialog(){this.OperateConectInfoVisible=!1,this.$emit("update:isShow",this.OperateConectInfoVisible)},requiredRules(e,o=this.$t("addOrModifyPgHba.qingshuru-neirong",[e]),n="blur"){return{required:!0,message:o,trigger:n}}},created(){this.OperateConectInfoVisible=this.$props.isShow,this.row=this.$props.dataRow},mounted(){this.activeName="connectCount"}},(function(){var e=this,o=e.$createElement,n=e._self._c||o;return n("el-dialog",{staticClass:"OperateConectInfoDialog",attrs:{"append-to-body":!0,title:e.$t("ConnectionPoolManagement.modify-title",[e.row.cluster_id,e.row.cluster_name,e.row.pool_id,e.row.pool_fe]),visible:e.OperateConectInfoVisible,"close-on-click-modal":!1},on:{close:e.closeDialog,"update:visible":function(o){e.OperateConectInfoVisible=o}}},[n("el-tabs",{model:{value:e.activeName,callback:function(o){e.activeName=o},expression:"activeName"}},[n("el-tab-pane",{attrs:{label:e.$t("ConnectionPoolManagement.xiugai-lianjieshu"),name:"connectCount"}},["connectCount"===e.activeName?n("modifyConnectPooll",{ref:"modifyConnectPooll",attrs:{"data-form-info":e.formInfo,"data-row":e.row}}):e._e()],1),n("el-tab-pane",{attrs:{label:e.$t("ConnectionPoolManagement.xiugai-qiandduan-lianjieshu"),name:"forwardConnectInfo"}},["forwardConnectInfo"===e.activeName?n("modifyConnectPooll",{ref:"modifyConnectPooll",attrs:{"data-form-info":e.formInfo,"data-row":e.row}}):e._e()],1),n("el-tab-pane",{attrs:{label:e.$t("ConnectionPoolManagement.xiugai-houdduan-lianjieshu"),name:"backConnectInfo"}},["backConnectInfo"===e.activeName?n("modifyConnectPooll",{ref:"modifyConnectPooll",attrs:{"data-form-info":e.formInfo,"data-row":e.row}}):e._e()],1),n("el-tab-pane",{attrs:{label:e.$t("ConnectionPoolManagement.tiaozheng-jiedian"),name:"adjustmentNodes"}},["adjustmentNodes"===e.activeName?n("modifyConnectPooll",{ref:"modifyConnectPooll",attrs:{"data-form-info":e.formInfo,"data-row":e.row}}):e._e()],1)],1),n("span",{staticClass:"dialog-footer",attrs:{slot:"footer"},slot:"footer"},[n("el-button",{on:{click:e.closeDialog}},[e._v(e._s(e.$t("index.qu-xiao")))]),"detail"!==e.row.method?n("el-button",{attrs:{type:"primary"},on:{click:e.submit}},[e._v(e._s(e.$t("defineDatabasePage.ti-jiao")))]):e._e()],1)],1)}),[],!1,s,"a532ef78",null,null);function s(e){for(let o in a)this[o]=a[o]}var r=function(){return i.exports}();export{r as default};
