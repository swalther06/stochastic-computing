
module mult #(parameter W = 4) (
    input [W-1:0] a,
    input [W-1:0] b,
    output [2*W-1:0] prod
);

assign prod = a * b;

endmodule



module bin_acc #(parameter W = 4) (
    input [W-1:0] a,
    input [W-1:0] b,
    output [2*W-1:0] acc

);

assign acc = a + b;

endmodule